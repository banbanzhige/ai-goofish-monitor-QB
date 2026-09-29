"""显式补齐本地任务稳定身份；不在普通读取或 Web 启动时改写旧配置。"""

from __future__ import annotations

import json
import hashlib
import logging
import os
from pathlib import Path
import tempfile
import uuid
from typing import Callable, TypeVar

from filelock import FileLock, Timeout

from src.portable.backup_archive import _assert_no_reparse_ancestry


logger = logging.getLogger(__name__)


class LocalTaskUpgradeError(RuntimeError):
    """本地升级拒绝或失败；不包含原始配置内容。"""


class LocalTaskConfigError(RuntimeError):
    """普通任务写入失败；原配置保持不变。"""


class LocalUpstreamStateError(RuntimeError):
    """本地 v2 旁文件缺失、损坏或并发冲突。"""


_JSON_STORES = frozenset({
    "hidden_items", "blacklist_rules", "view_preferences", "criteria_generation_jobs",
})
_STORE_FILES = {name + ".json" for name in _JSON_STORES} | {
    "version.json", "price_observations.jsonl", ".store.lock",
}
_MAX_JSON_BYTES = 32 * 1024 * 1024
_MAX_PRICE_BYTES = 128 * 1024 * 1024
_PRICE_KEY_FIELDS = ("task_ref", "item_id", "run_id")


class LocalUpstreamStore:
    """只管理固定 `local_admin` 空间，不映射 PostgreSQL 的用户 UUID。"""

    def __init__(self, data_root: Path):
        if not data_root.is_absolute():
            raise LocalUpstreamStateError("local upstream data root must be absolute")
        self.root = data_root / "state" / "upstream" / "v2"

    def initialize(self) -> None:
        """显式创建完整空结构；一次目录改名提交，不覆盖已有状态。"""

        parent = self.root.parent
        stage: Path | None = None
        try:
            parent.mkdir(parents=True, exist_ok=True)
            _assert_no_reparse_ancestry(parent, Path(parent.anchor))
            if self.root.exists() or self.root.is_symlink():
                raise LocalUpstreamStateError("local upstream v2 state already exists")
            stage = Path(tempfile.mkdtemp(prefix=".v2-stage-", dir=parent))
            (stage / "version.json").write_text(
                '{"schema_version":2,"owner_id":"local_admin"}\n', encoding="utf-8")
            for name in _JSON_STORES:
                (stage / (name + ".json")).write_text(
                    '{"format_version":2,"owner_id":"local_admin","revision":0,"records":[]}\n',
                    encoding="utf-8")
            (stage / "price_observations.jsonl").write_bytes(b"")
            (stage / ".store.lock").write_bytes(b"")
            os.rename(stage, self.root)
            stage = None
        except LocalUpstreamStateError:
            raise
        except Exception:
            logger.error("Local upstream v2 initialization failed",
                         extra={"event": "local_upstream_initialize_failed"})
            raise LocalUpstreamStateError("local upstream v2 initialization failed safely") from None
        finally:
            if stage is not None:
                try:
                    for child in stage.iterdir():
                        child.unlink()
                    stage.rmdir()
                except OSError:
                    logger.warning("Local upstream initialization stage cleanup failed",
                                   extra={"event": "local_upstream_stage_cleanup_failed"})

    def _validated_root(self) -> None:
        try:
            _assert_no_reparse_ancestry(self.root, Path(self.root.anchor))
            actual = {item.name for item in self.root.iterdir()}
            if actual != _STORE_FILES:
                raise LocalUpstreamStateError("local upstream v2 file set differs")
            for item in self.root.iterdir():
                _assert_no_reparse_ancestry(item, self.root)
                if not item.is_file():
                    raise LocalUpstreamStateError("local upstream v2 contains a non-file entry")
            marker = json.loads((self.root / "version.json").read_text(encoding="utf-8"))
            if marker != {"schema_version": 2, "owner_id": "local_admin"}:
                raise LocalUpstreamStateError("local upstream v2 marker differs")
        except LocalUpstreamStateError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise LocalUpstreamStateError("local upstream v2 state cannot be verified") from None

    def _read_json(self, name: str) -> dict:
        path = self.root / (name + ".json")
        try:
            if path.stat().st_size > _MAX_JSON_BYTES:
                raise LocalUpstreamStateError("local upstream v2 JSON limit exceeded")
            value = json.loads(path.read_text(encoding="utf-8"))
        except LocalUpstreamStateError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise LocalUpstreamStateError("local upstream v2 JSON is invalid") from None
        if (not isinstance(value, dict) or set(value) != {
                "format_version", "owner_id", "revision", "records"}
            or value["format_version"] != 2 or value["owner_id"] != "local_admin"
            or type(value["revision"]) is not int or value["revision"] < 0
            or not isinstance(value["records"], list)
            or len(value["records"]) > 100_000
            or any(not isinstance(record, dict) for record in value["records"])):
            raise LocalUpstreamStateError("local upstream v2 JSON structure differs")
        return value

    def read(self, name: str) -> dict:
        if name not in _JSON_STORES:
            raise LocalUpstreamStateError("unknown local upstream store")
        try:
            with FileLock(str(self.root / ".store.lock"), timeout=30):
                self._validated_root()
                return self._read_json(name)
        except LocalUpstreamStateError:
            raise
        except (OSError, Timeout):
            raise LocalUpstreamStateError("local upstream v2 state cannot be read safely") from None

    def read_many(self, names: tuple[str, ...]) -> dict[str, dict]:
        """在同一把跨进程锁内读取结果视图所需的同一版本快照。"""
        if not names or any(name not in _JSON_STORES for name in names):
            raise LocalUpstreamStateError("unknown local upstream store")
        try:
            with FileLock(str(self.root / ".store.lock"), timeout=30):
                self._validated_root()
                return {name: self._read_json(name) for name in names}
        except LocalUpstreamStateError:
            raise
        except (OSError, Timeout):
            raise LocalUpstreamStateError("local upstream v2 state cannot be read safely") from None

    def update(self, name: str, *, expected_revision: int,
               transform: Callable[[list[dict]], list[dict]]) -> int:
        """同一文件锁内 CAS 修改；临时文件落盘后原子替换。"""

        if name not in _JSON_STORES or not callable(transform):
            raise LocalUpstreamStateError("invalid local upstream update")
        temporary: Path | None = None
        try:
            with FileLock(str(self.root / ".store.lock"), timeout=30):
                self._validated_root()
                current = self._read_json(name)
                if type(expected_revision) is not int or current["revision"] != expected_revision:
                    raise LocalUpstreamStateError("local upstream revision conflict")
                records = transform([dict(item) for item in current["records"]])
                if (not isinstance(records, list) or len(records) > 100_000
                    or any(not isinstance(item, dict) for item in records)):
                    raise LocalUpstreamStateError("local upstream update returned invalid records")
                updated = {**current, "revision": expected_revision + 1, "records": records}
                descriptor, name_on_disk = tempfile.mkstemp(
                    prefix="." + name + "-", suffix=".tmp", dir=self.root)
                temporary = Path(name_on_disk)
                with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                    json.dump(updated, stream, ensure_ascii=False, separators=(",", ":"))
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                if temporary.stat().st_size > _MAX_JSON_BYTES:
                    raise LocalUpstreamStateError("local upstream v2 JSON limit exceeded")
                os.replace(temporary, self.root / (name + ".json"))
                temporary = None
                return updated["revision"]
        except LocalUpstreamStateError:
            raise
        except Timeout:
            raise LocalUpstreamStateError("local upstream v2 state is busy") from None
        except Exception:
            logger.error("Local upstream v2 update failed", extra={"event": "local_upstream_update_failed"})
            raise LocalUpstreamStateError("local upstream v2 update failed safely") from None
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Local upstream v2 temporary cleanup failed",
                                   extra={"event": "local_upstream_temp_cleanup_failed"})

    def _read_prices(self) -> tuple[list[dict], set[tuple[str, str, str]], bytes]:
        path = self.root / "price_observations.jsonl"
        try:
            if path.stat().st_size > _MAX_PRICE_BYTES:
                raise LocalUpstreamStateError("local price observation limit exceeded")
            content = path.read_bytes()
            if content and not content.endswith(b"\n"):
                raise LocalUpstreamStateError("local price observation tail is incomplete")
            records = [json.loads(line.decode("utf-8")) for line in content.splitlines()]
        except LocalUpstreamStateError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise LocalUpstreamStateError("local price observations cannot be verified") from None
        keys: set[tuple[str, str, str]] = set()
        for record in records:
            key = self._price_key(record)
            if key in keys:
                raise LocalUpstreamStateError("local price observation key is duplicated")
            keys.add(key)
        return records, keys, content

    @staticmethod
    def _price_key(record: dict) -> tuple[str, str, str]:
        if not isinstance(record, dict) or record.get("owner_id") != "local_admin":
            raise LocalUpstreamStateError("local price observation owner is invalid")
        key = tuple(record.get(field) for field in _PRICE_KEY_FIELDS)
        if any(not isinstance(value, str) or not value or len(value) > 128 for value in key):
            raise LocalUpstreamStateError("local price observation key is invalid")
        for value in (key[0], key[2]):
            try:
                if str(uuid.UUID(value)) != value:
                    raise ValueError
            except (TypeError, ValueError, AttributeError):
                raise LocalUpstreamStateError("local price observation identity is invalid") from None
        return key

    def read_price_observations(self) -> list[dict]:
        """从完整已提交日志重建索引；损坏尾行不被当成有效记录。"""

        try:
            with FileLock(str(self.root / ".store.lock"), timeout=30):
                self._validated_root()
                records, _, _ = self._read_prices()
                return records
        except LocalUpstreamStateError:
            raise
        except (OSError, Timeout):
            raise LocalUpstreamStateError("local price observations cannot be read safely") from None

    def iter_price_observations(self):
        """锁内校验后逐行读取；消费方提前关闭即停止磁盘读取。"""
        try:
            with FileLock(str(self.root / ".store.lock"), timeout=30):
                self._validated_root()
                path = self.root / "price_observations.jsonl"
                if path.stat().st_size > _MAX_PRICE_BYTES:
                    raise LocalUpstreamStateError("local price observation limit exceeded")
                keys = set()
                with path.open("rb") as stream:
                    for line in stream:
                        if not line.endswith(b"\n"):
                            raise LocalUpstreamStateError("local price observation tail is incomplete")
                        try:
                            record = json.loads(line.decode("utf-8"))
                        except (UnicodeError, json.JSONDecodeError):
                            raise LocalUpstreamStateError("local price observations cannot be verified") from None
                        key = self._price_key(record)
                        if key in keys:
                            raise LocalUpstreamStateError("local price observation key is duplicated")
                        keys.add(key)
                        yield record
        except LocalUpstreamStateError:
            raise
        except (OSError, Timeout, UnicodeError, json.JSONDecodeError):
            raise LocalUpstreamStateError("local price observations cannot be read safely") from None

    def append_price_observation(self, observation: dict) -> bool:
        """跨进程锁内按三元键去重，整份有界日志原子替换以避免断电半行。"""

        record = dict(observation) if isinstance(observation, dict) else observation
        key = self._price_key(record)
        try:
            line = (json.dumps(record, ensure_ascii=False, separators=(",", ":"),
                               allow_nan=False) + "\n").encode("utf-8")
        except (TypeError, ValueError, UnicodeError):
            raise LocalUpstreamStateError("local price observation cannot be encoded") from None
        if len(line) > 16 * 1024:
            raise LocalUpstreamStateError("local price observation exceeds the record limit")
        temporary: Path | None = None
        try:
            with FileLock(str(self.root / ".store.lock"), timeout=30):
                self._validated_root()
                _, keys, content = self._read_prices()
                if key in keys:
                    return False
                if len(content) + len(line) > _MAX_PRICE_BYTES:
                    raise LocalUpstreamStateError("local price observation limit exceeded")
                descriptor, name = tempfile.mkstemp(
                    prefix=".price-observations-", suffix=".tmp", dir=self.root)
                temporary = Path(name)
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(content)
                    stream.write(line)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.root / "price_observations.jsonl")
                temporary = None
                return True
        except LocalUpstreamStateError:
            raise
        except Timeout:
            raise LocalUpstreamStateError("local price observation store is busy") from None
        except Exception:
            logger.error("Local price observation append failed",
                         extra={"event": "local_price_observation_append_failed"})
            raise LocalUpstreamStateError("local price observation append failed safely") from None
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Local price observation temporary cleanup failed",
                                   extra={"event": "local_price_observation_temp_cleanup_failed"})


def _validate_task_list(tasks: object) -> list[dict]:
    if not isinstance(tasks, list) or any(not isinstance(task, dict) for task in tasks):
        raise LocalTaskUpgradeError("local task configuration must be a task list")
    seen: set[str] = set()
    for task in tasks:
        if not isinstance(task.get("task_name"), str) or not task["task_name"]:
            raise LocalTaskUpgradeError("local task name is invalid")
        identity = task.get("stable_task_id")
        if identity is None:
            continue
        try:
            normalized = str(uuid.UUID(identity))
        except (TypeError, ValueError, AttributeError):
            raise LocalTaskUpgradeError("local task stable identity is invalid") from None
        if identity != normalized or identity in seen:
            raise LocalTaskUpgradeError("local task stable identity is invalid or duplicated")
        seen.add(identity)
    return tasks


def _validated_tasks(config_path: Path) -> list[dict]:
    try:
        tasks = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise LocalTaskUpgradeError("local task configuration cannot be read safely") from None
    return _validate_task_list(tasks)


_T = TypeVar("_T")


def mutate_local_task_config(
    config_path: Path, transform: Callable[[list[dict]], tuple[_T, bool]],
    *, create_if_missing: bool = False,
) -> _T:
    """普通写入与显式身份升级共用锁；回调在锁内读改写。"""

    path = config_path.absolute()
    temporary: Path | None = None
    try:
        if not callable(transform):
            raise LocalTaskConfigError("local task transform is invalid")
        _assert_no_reparse_ancestry(path.parent, Path(path.anchor))
        if not path.parent.is_dir():
            raise LocalTaskConfigError("local task configuration parent is missing")
        with FileLock(str(path.with_name(path.name + ".lock")), timeout=30):
            if path.exists() or path.is_symlink():
                _assert_no_reparse_ancestry(path, Path(path.anchor))
                tasks = _validated_tasks(path)
            elif create_if_missing:
                tasks = []
            else:
                raise LocalTaskConfigError("local task configuration is missing")
            outcome, changed = transform(tasks)
            if not changed:
                return outcome
            _validate_task_list(tasks)
            descriptor, name = tempfile.mkstemp(prefix=".config-task-", suffix=".tmp",
                                                dir=path.parent)
            temporary = Path(name)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(tasks, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            temporary = None
            return outcome
    except (LocalTaskConfigError, LocalTaskUpgradeError):
        raise
    except Timeout:
        raise LocalTaskConfigError("local task configuration is busy") from None
    except Exception:
        logger.error("Local task configuration update failed",
                     extra={"event": "local_task_config_update_failed"})
        raise LocalTaskConfigError("local task configuration update failed safely") from None
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                logger.warning("Local task configuration temporary cleanup failed",
                               extra={"event": "local_task_config_temp_cleanup_failed"})


def upgrade_local_task_ids(config_path: Path, *, verify_maintenance: Callable[[], None],
                           verify_backup: Callable[[], None]) -> int:
    """在锁内原子补齐旧任务 UUID；调用方必须证明停写和已有可恢复备份。"""

    if not callable(verify_maintenance) or not callable(verify_backup):
        raise LocalTaskUpgradeError("local task upgrade requires maintenance and backup proof")
    if not config_path.is_absolute() or not config_path.is_file():
        raise LocalTaskUpgradeError("local task configuration path is invalid")
    try:
        _assert_no_reparse_ancestry(config_path, Path(config_path.anchor))
    except Exception:
        raise LocalTaskUpgradeError("local task configuration path cannot be verified") from None
    lock_path = config_path.with_name(config_path.name + ".lock")
    temporary: Path | None = None
    try:
        with FileLock(str(lock_path), timeout=30):
            verify_maintenance()
            verify_backup()
            tasks = _validated_tasks(config_path)
            added = 0
            for task in tasks:
                if task.get("stable_task_id") is None:
                    task["stable_task_id"] = str(uuid.uuid4())
                    added += 1
            if not added:
                return 0
            verify_maintenance()
            descriptor, name = tempfile.mkstemp(prefix=".config-v2-", suffix=".tmp",
                                                dir=config_path.parent)
            temporary = Path(name)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(tasks, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, config_path)
            temporary = None
            return added
    except LocalTaskUpgradeError:
        raise
    except Timeout:
        raise LocalTaskUpgradeError("local task configuration is busy") from None
    except Exception:
        logger.error("Local task identity upgrade failed", extra={"event": "local_task_identity_upgrade_failed"})
        raise LocalTaskUpgradeError("local task identity upgrade failed safely") from None
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                logger.warning("Local task identity temporary cleanup failed",
                               extra={"event": "local_task_identity_cleanup_failed"})


def upgrade_local_data(config_path: Path, data_root: Path, backup_path: Path, backup_sha256: str,
                       *, verify_maintenance: Callable[[], None]) -> int:
    """显式升级本地任务身份和空 v2 旁文件；备份必须是配置的逐字节副本。"""

    if (not all(path.is_absolute() for path in (config_path, data_root, backup_path))
        or not callable(verify_maintenance)
        or len(backup_sha256) != 64
        or set(backup_sha256) - set("0123456789abcdef")):
        raise LocalTaskUpgradeError("local upgrade inputs are invalid")
    try:
        _assert_no_reparse_ancestry(config_path, Path(config_path.anchor))
        _assert_no_reparse_ancestry(data_root, Path(data_root.anchor))
        _assert_no_reparse_ancestry(backup_path, Path(backup_path.anchor))
        root_resolved = data_root.resolve(strict=True)
        config_resolved = config_path.resolve(strict=True)
        backup_resolved = backup_path.resolve(strict=True)
    except Exception:
        raise LocalTaskUpgradeError("local upgrade paths cannot be verified") from None
    if backup_resolved == root_resolved or root_resolved in backup_resolved.parents:
        raise LocalTaskUpgradeError("local upgrade backup must be outside the data root")
    if config_resolved not in (root_resolved / "config.json", root_resolved / "config" / "config.json"):
        raise LocalTaskUpgradeError("local upgrade config must be the selected data root config")

    def verify_backup() -> None:
        try:
            if not backup_path.is_file() or not config_path.is_file():
                raise LocalTaskUpgradeError("local upgrade backup or config is missing")
            def digest(path: Path) -> str:
                value = hashlib.sha256()
                with path.open("rb") as stream:
                    while block := stream.read(1024 * 1024):
                        value.update(block)
                return value.hexdigest()
            if digest(backup_path) != backup_sha256 or digest(config_path) != backup_sha256:
                raise LocalTaskUpgradeError("local upgrade backup differs from current config")
        except LocalTaskUpgradeError:
            raise
        except OSError:
            raise LocalTaskUpgradeError("local upgrade backup cannot be verified") from None

    verify_maintenance()
    verify_backup()
    store = LocalUpstreamStore(data_root)
    if store.root.exists() or store.root.is_symlink():
        for name in _JSON_STORES:
            store.read(name)
        store.read_price_observations()
    else:
        store.initialize()
    return upgrade_local_task_ids(config_path, verify_maintenance=verify_maintenance,
                                  verify_backup=verify_backup)
