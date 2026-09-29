"""Build a preview-only Windows portable bundle from already verified components.

This is a packaging tool for maintainers, not the end-user launcher.  It never
downloads components or reads user configuration, and it deliberately rejects
unknown/stale component layouts rather than trying to repair them.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from email.parser import Parser
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import sys
import uuid
import zipfile
from dataclasses import dataclass
from typing import Any, Iterable

_NOTICE_CONTRACT_SPEC = importlib.util.spec_from_file_location(
    "_portable_notice_contract", Path(__file__).with_name("portable_notice_contract.py")
)
if _NOTICE_CONTRACT_SPEC is None or _NOTICE_CONTRACT_SPEC.loader is None:
    raise RuntimeError("portable notice contract could not be loaded")
_NOTICE_CONTRACT = importlib.util.module_from_spec(_NOTICE_CONTRACT_SPEC)
_NOTICE_CONTRACT_SPEC.loader.exec_module(_NOTICE_CONTRACT)
EXPECTED_WHEEL_NOTICE_COUNT = _NOTICE_CONTRACT.EXPECTED_WHEEL_NOTICE_COUNT
REQUIRED_NON_WHEEL_COMPONENTS = _NOTICE_CONTRACT.REQUIRED_NON_WHEEL_COMPONENTS
canonicalize_distribution = _NOTICE_CONTRACT.canonicalize_distribution
load_locked_distributions = _NOTICE_CONTRACT.load_locked_distributions
validate_notice_inventory = _NOTICE_CONTRACT.validate_notice_inventory

_LAUNCHER_INVENTORY_SPEC = importlib.util.spec_from_file_location(
    "_portable_launcher_inventory", Path(__file__).with_name("launcher_publish_inventory.py")
)
if _LAUNCHER_INVENTORY_SPEC is None or _LAUNCHER_INVENTORY_SPEC.loader is None:
    raise RuntimeError("Launcher publish inventory helper could not be loaded")
_LAUNCHER_INVENTORY = importlib.util.module_from_spec(_LAUNCHER_INVENTORY_SPEC)
_LAUNCHER_INVENTORY_SPEC.loader.exec_module(_LAUNCHER_INVENTORY)


_ROOT = Path(__file__).resolve().parents[2]
_LAYOUT_PATH = Path(__file__).with_name("portable-bundle-layout.json")
_MIN_FREE_BYTES = 10 * 1024**3
_MIN_FREE_RATIO = 0.05
_REVIEWED_REPOSITORY_NOTICE_SOURCES = {
    ("avalonia-ui", "12.1.2", "scripts/portable/third-party-notices/avalonia-MIT.txt"):
        "213814d306090074d234d760239ff0f67eb9b8d20eefb4d5631bb39dbe0b769b",
    ("chromium", "143 / r1200", "scripts/portable/third-party-notices/chromium-143-r1200-credits.html"):
        "baac582df59212838afdd377fd757412e79d3865d7ff2e7c2b9f898e6513cd6b",
    ("chromium-onnxruntime-headers", "v1.23.0", "scripts/portable/third-party-notices/onnxruntime-headers-v1.23.0-MIT.txt"):
        "2f07c72751aed99790b8a4869cf2311df85a860b22ded05fa22803587a48922c",
}
_PYTHON_SITE_PACKAGES = (
    ".tmp/dependencies/portable-python/python-3.13.15-e67c6b779c81-windows-x64/site-packages"
)
_NOTICE_FILE_NAME = re.compile(r"(?i)(license|licence|notice|copying|copyright|patent)")
_RELEASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_INCOMPLETE_MARKER = ".bundle-build-incomplete"
_SOURCE_ENTRYPOINTS = (
    "collector.py",
    "login.py",
    "portable_provision.py",
    "portable_schema.py",
    "portable_server.py",
    "portable_web.py",
    "portable_backup.py",
    "portable_restore.py",
    "portable_migrate.py",
    "web_server.py",
    "scripts/portable/python-bootstrap.py",
    "License",
)
_HEAD_DEFAULTS = ("prompts/base_prompt.txt", "prompts/bayes/bayes_v1.json")
_GUIDES = ("prompts/guide/bayes_guide.md", "prompts/guide/weight_framework_guide.md")


class BundleError(RuntimeError):
    """The bundle cannot be planned or assembled safely."""


@dataclass(frozen=True)
class PlannedFile:
    source: Path | None
    destination: str
    size: int
    sha256: str | None = None
    head_blob: str | None = None
    content: bytes | None = None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise BundleError(f"could not hash {path.name}") from exc
    return digest.hexdigest()


def _safe_relative(value: str) -> str:
    if value.startswith("./"):
        value = value[2:]
    windows = PureWindowsPath(value)
    parts = value.split("/")
    if not value or "\\" in value or windows.anchor or any(
        part in {"", ".", ".."} or ":" in part or part.rstrip(". ") != part
        or any(c in part for c in '<>"|?*') or any(ord(c) < 32 for c in part)
        or re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?", part, re.IGNORECASE)
        for part in parts
    ):
        raise BundleError("relative path is unsafe")
    return value


def _is_reparse(path: Path) -> bool:
    try:
        return path.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(path))
    except OSError as exc:
        raise BundleError(f"could not inspect reparse state for {path}") from exc


def _assert_safe_tree(root: Path) -> None:
    _assert_safe_ancestors(root)
    try:
        resolved = root.resolve(strict=True)
    except OSError as exc:
        raise BundleError(f"path does not exist: {root}") from exc
    if _is_reparse(root):
        raise BundleError(f"reparse-point root is not allowed: {root}")
    for candidate in (resolved, *resolved.rglob("*")):
        if _is_reparse(candidate):
            raise BundleError(f"reparse point is not allowed: {candidate}")


def _assert_safe_ancestors(path: Path) -> None:
    for candidate in (path, *path.parents):
        if _is_reparse(candidate):
            raise BundleError("reparse-point ancestor is not allowed")


def _within(root: Path, candidate: Path) -> Path:
    try:
        return candidate.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise BundleError(f"path escapes its allowed root: {candidate}") from exc


def _load_json(path: Path) -> dict[str, Any]:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"could not read JSON file: {path.name}") from exc
    if not isinstance(content, dict):
        raise BundleError(f"JSON object required: {path.name}")
    return content


def _component_id(path: Path) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,119}", path.name):
        raise BundleError(f"component directory name is unsafe: {path.name}")
    return path.name


def _run_verifier(arguments: list[str]) -> None:
    # Inspect with the maintainer's running interpreter, without site imports;
    # never execute the runtime being checked before its integrity is established.
    arguments = [sys.executable, "-I", "-S", *arguments[1:]]
    try:
        completed = subprocess.run(arguments, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8", errors="replace", timeout=180, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise BundleError("component verifier could not be started") from exc
    if completed.returncode != 0:
        raise BundleError("component verifier rejected its runtime")


def _verify_postgres(runtime: Path, archive: Path, lock_path: Path) -> None:
    lock = _load_json(lock_path)
    if lock.get("component") != "postgresql" or lock.get("schema_version") != 1:
        raise BundleError("PostgreSQL lock is unsupported")
    if not archive.is_file() or archive.stat().st_size != lock.get("archive_bytes") or _sha256(archive) != lock.get("sha256"):
        raise BundleError("PostgreSQL archive does not match its lock")
    _assert_safe_tree(runtime)
    prefixes = tuple(str(value) for value in lock.get("selected_archive_prefixes", []))
    exact = {str(value) for value in lock.get("selected_archive_files", [])}
    expected: set[str] = set()
    selected_bytes = 0
    try:
        with zipfile.ZipFile(archive) as source:
            for entry in source.infolist():
                if entry.is_dir():
                    continue
                selected = entry.filename in exact or any(entry.filename.startswith(prefix) for prefix in prefixes)
                if not selected:
                    continue
                if not entry.filename.startswith("pgsql/") or ".." in Path(entry.filename).parts:
                    raise BundleError("PostgreSQL archive selection has an unsafe path")
                relative = entry.filename.removeprefix("pgsql/")
                installed = runtime / relative
                if not installed.is_file():
                    raise BundleError("PostgreSQL runtime file is missing")
                with source.open(entry) as archived, installed.open("rb") as present:
                    while True:
                        left = archived.read(1024 * 1024)
                        right = present.read(1024 * 1024)
                        if left != right:
                            raise BundleError("PostgreSQL runtime differs from locked archive")
                        if not left:
                            break
                expected.add(Path(relative).as_posix())
                selected_bytes += entry.file_size
    except (OSError, zipfile.BadZipFile) as exc:
        raise BundleError("PostgreSQL archive verification failed") from exc
    actual = {path.relative_to(runtime).as_posix() for path in runtime.rglob("*") if path.is_file()}
    if actual != expected or len(actual) != lock.get("runtime_files") or selected_bytes != lock.get("runtime_bytes"):
        raise BundleError("PostgreSQL runtime file set does not match its lock")


def _git_head_blob(relative: str) -> bytes:
    _safe_relative(relative)
    try:
        completed = subprocess.run(["git", "show", f"HEAD:{relative}"], cwd=_ROOT, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise BundleError("Git HEAD blob could not be read for bundle defaults") from exc
    if completed.returncode != 0:
        raise BundleError(f"required tracked default is unavailable in Git HEAD: {relative}")
    return completed.stdout


def _source_files(source_root: Path) -> list[PlannedFile]:
    _assert_safe_ancestors(source_root)
    try:
        tracked_result = subprocess.run(["git", "ls-files", "-z", "--", "src", "static", "templates"], cwd=source_root,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=30)
        tracked = set(tracked_result.stdout.decode("utf-8").split("\0"))
    except (OSError, UnicodeError, subprocess.SubprocessError) as exc:
        raise BundleError("could not determine tracked program assets") from exc
    planned: list[PlannedFile] = []
    for relative in _SOURCE_ENTRYPOINTS:
        candidate = source_root / relative
        if not candidate.is_file():
            raise BundleError(f"required program entrypoint is missing: {relative}")
        _assert_safe_ancestors(candidate)
        planned.append(PlannedFile(candidate, relative, candidate.stat().st_size))
    for tree, destination_root in (("src", "src"), ("static", "static"), ("templates", "templates")):
        root = source_root / tree
        if not root.is_dir():
            raise BundleError(f"required program tree is missing: {tree}")
        for candidate in root.rglob("*"):
            if _is_reparse(candidate):
                raise BundleError("program source contains a reparse point")
            if not candidate.is_file():
                continue
            relative = candidate.relative_to(source_root).as_posix()
            if tree == "src" and candidate.suffix != ".py":
                continue
            parts = Path(relative).parts
            if ("__pycache__" in parts or "tests" in parts or relative.startswith("static/avatars/")
                or relative == "src/storage/server_migration.py"):
                # PG15 server administration is not a Launcher runtime asset.
                continue
            if relative not in tracked and not (
                relative.startswith("src/portable/") and candidate.suffix == ".py"
                or relative in {"src/runtime_paths.py", "src/log_retention.py", "src/account_policy.py", "src/web/account_models.py", "src/storage/upstream_local.py", "src/storage/result_management.py", "src/storage/price_observations.py", "src/web/result_filters.py", "src/web/result_management.py", "src/web/price_observations.py", "static/js/account_policy.js", "templates/portable_setup.html", "static/portable/setup.js", "static/portable/setup.css"}
            ):
                raise BundleError("untracked program asset requires an explicit build allow-list entry")
            if candidate.name.startswith(".") or candidate.suffix.lower() in {".log", ".bak", ".zip", ".tmp", ".env"}:
                raise BundleError("unexpected private or temporary file in program assets")
            _assert_safe_ancestors(candidate)
            planned.append(PlannedFile(candidate, relative, candidate.stat().st_size))
    for relative in ("images/login-bg.png",):
        candidate = source_root / relative
        if not candidate.is_file():
            raise BundleError(f"required public image is missing: {relative}")
        planned.append(PlannedFile(candidate, relative, candidate.stat().st_size))
    logo_root = source_root / "images" / "logo"
    if not logo_root.is_dir():
        raise BundleError("public logo directory is missing")
    for name in ("favicon 32x32.png", "logo 128x128.png", "logo 2048x2048.png", "banner.png"):
        candidate = logo_root / name
        if not candidate.is_file():
            raise BundleError("required branding asset is missing")
        _assert_safe_ancestors(candidate)
        relative = candidate.relative_to(source_root).as_posix()
        planned.append(PlannedFile(candidate, relative, candidate.stat().st_size))
    for relative in _GUIDES:
        candidate = source_root / relative
        if not candidate.is_file():
            raise BundleError(f"required guide is missing: {relative}")
        planned.append(PlannedFile(candidate, relative, candidate.stat().st_size))
    for relative in _HEAD_DEFAULTS:
        content = _git_head_blob(relative)
        planned.append(PlannedFile(None, "defaults/" + relative, len(content), hashlib.sha256(content).hexdigest(), head_blob=relative))
    seed_manifest = {"format_version":1, "files":[
        {"path":item.destination.removeprefix("defaults/"), "kind":"bayes" if item.destination.endswith(".json") else "prompt",
         "size":item.size,"sha256":item.sha256} for item in planned if item.head_blob is not None
    ]}
    manifest_bytes = (json.dumps(seed_manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    planned.append(PlannedFile(None, "defaults/seed_manifest.json", len(manifest_bytes), hashlib.sha256(manifest_bytes).hexdigest(), content=manifest_bytes))
    return _deduplicate(planned)


def _deduplicate(files: Iterable[PlannedFile]) -> list[PlannedFile]:
    result: dict[str, PlannedFile] = {}
    for item in files:
        normalized = _safe_relative(item.destination)
        key = normalized.casefold()
        if key in result:
            raise BundleError(f"duplicate bundle destination: {item.destination}")
        result[key] = PlannedFile(item.source, normalized, item.size, item.sha256, item.head_blob, item.content)
    return [result[key] for key in sorted(result)]


def _tree_files(source: Path, destination_root: str) -> list[PlannedFile]:
    _assert_safe_tree(source)
    result = []
    for candidate in source.rglob("*"):
        if candidate.is_file():
            relative = candidate.relative_to(source).as_posix()
            result.append(PlannedFile(candidate, f"{destination_root}/{relative}", candidate.stat().st_size, _sha256(candidate)))
    return result


def _launcher_files(source: Path, receipt: Path) -> list[PlannedFile]:
    try:
        inventory = _LAUNCHER_INVENTORY.verify_inventory(_ROOT, source, receipt)
    except _LAUNCHER_INVENTORY.InventoryError as exc:
        raise BundleError(f"Launcher publish input rejected: {exc}") from exc
    reserved = {"bundle-manifest.json", "current.json", _INCOMPLETE_MARKER}
    for item in inventory:
        if item["path"].casefold() in reserved:
            raise BundleError("Launcher publish input collides with bundle metadata")
    return [PlannedFile(source / item["path"], f"launcher/{item['path']}", item["size"], item["sha256"])
            for item in inventory]


def _root_launch_entry(apphost: Path) -> PlannedFile:
    """Point a second copy of the SDK-produced apphost at the managed DLL in launcher/."""
    try:
        image = apphost.read_bytes()
    except OSError as exc:
        raise BundleError("Launcher apphost could not be read") from exc
    original = b"AiGoofish.Launcher.App.dll"
    target = b"launcher\\AiGoofish.Launcher.App.dll"
    if not image.startswith(b"MZ") or image.count(original) != 1:
        raise BundleError("Launcher apphost does not contain the expected application path")
    offset = image.index(original)
    if image[offset + len(original):offset + len(target)] != bytes(len(target) - len(original)):
        raise BundleError("Launcher apphost path slot cannot hold the root entry target")
    patched = image[:offset] + target + image[offset + len(target):]
    return PlannedFile(None, "AiGoofish.exe", len(patched), hashlib.sha256(patched).hexdigest(), content=patched)


def _validate_required_notice_components(components: Any) -> None:
    if not isinstance(components, list):
        raise BundleError("notice inventory components are malformed")
    contract_components = []
    complete = bool(components)
    for entry in components:
        if not isinstance(entry, dict):
            raise BundleError("notice inventory component entry is malformed")
        if entry.get("evidence_verified") is not True or entry.get("is_gap") is not False:
            complete = False
        contract_entry = dict(entry)
        if isinstance(entry.get("component"), str) and entry["component"] in REQUIRED_NON_WHEEL_COMPONENTS:
            _, filename, _ = REQUIRED_NON_WHEEL_COMPONENTS[entry["component"]]
            contract_entry["file"] = f"third-party-notices/{entry['component']}/{filename}"
            contract_entry["sha256"] = entry.get("evidence_sha256")
        contract_components.append(contract_entry)
    inventory = {"format_version": 1, "notice_complete": complete, "components": contract_components}
    lock_path = _ROOT / "scripts/portable/requirements-python.lock.txt"
    site_packages = _ROOT / _PYTHON_SITE_PACKAGES
    try:
        locked = load_locked_distributions(lock_path)
        dist_infos = sorted(path for path in site_packages.glob("*.dist-info") if path.is_dir())
        metadata_by_distribution: dict[str, tuple[str, str, Path, Any]] = {}
        notice_sources: dict[str, tuple[Path, Path, list[str]]] = {}
        for dist_info in dist_infos:
            _assert_safe_tree(dist_info)
            metadata_path = dist_info / "METADATA"
            try:
                metadata = Parser().parsestr(metadata_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError) as exc:
                raise BundleError("locked Python distribution metadata is unreadable") from exc
            name, version = metadata.get("Name"), metadata.get("Version")
            if not name or not version:
                raise BundleError("locked Python distribution metadata lacks Name or Version")
            canonical = canonicalize_distribution(name)
            if canonical in metadata_by_distribution:
                raise BundleError("Python runtime contains duplicate distribution metadata")
            if canonical not in locked or locked[canonical][1] != version:
                raise BundleError("Python distribution metadata differs from requirements lock")
            metadata_by_distribution[canonical] = (name, version, dist_info, metadata)
            declared_license_files = metadata.get_all("License-File", []) or []
            for candidate in dist_info.rglob("*"):
                if not candidate.is_file() or not _NOTICE_FILE_NAME.search(candidate.name):
                    continue
                _assert_safe_ancestors(candidate)
                relative = candidate.relative_to(site_packages).as_posix()
                notice_sources[relative] = (candidate, dist_info, declared_license_files)
    except OSError as exc:
        raise BundleError("locked Python notice sources could not be enumerated") from exc
    if set(metadata_by_distribution) != set(locked) or len(metadata_by_distribution) != 60:
        raise BundleError("Python runtime distributions differ from the locked 60 distributions")
    if len(notice_sources) != EXPECTED_WHEEL_NOTICE_COUNT:
        raise BundleError("Python runtime does not contain the locked 93 wheel notice files")
    try:
        validate_notice_inventory(inventory, lock_path, allow_incomplete_preview=True)
    except ValueError as exc:
        raise BundleError(str(exc)) from exc

    wheel_entries = [entry for entry in components if entry["component"].startswith("python-wheel-")]
    inventory_sources: set[str] = set()
    for entry in wheel_entries:
        source_relative = entry.get("notice_source")
        cache_relative = entry.get("cache_relative_path")
        distribution = entry.get("distribution")
        if not all(isinstance(value, str) for value in (source_relative, cache_relative, distribution)):
            raise BundleError("Python wheel notice lacks its locked source identity")
        try:
            source_relative = _safe_relative(source_relative)
            cache_relative = _safe_relative(cache_relative)
        except BundleError as exc:
            raise BundleError("Python wheel notice source identity is unsafe") from exc
        expected_cache_relative = source_relative.removeprefix(_PYTHON_SITE_PACKAGES + "/")
        if expected_cache_relative == source_relative or expected_cache_relative != cache_relative:
            raise BundleError("Python wheel notice cache path does not match its source")
        source = _ROOT / source_relative
        found = notice_sources.get(cache_relative)
        if found is None or found[0] != source:
            raise BundleError("Python wheel notice source is absent from the locked runtime")
        metadata_name, metadata_version, dist_info, metadata = metadata_by_distribution[
            canonicalize_distribution(distribution)
        ]
        if distribution != metadata_name or entry.get("version") != metadata_version:
            raise BundleError("Python wheel notice distribution/version differs from METADATA")
        if source.parent != dist_info and dist_info not in source.parents:
            raise BundleError("Python wheel notice source is outside its distribution metadata")
        if (entry.get("metadata_license_files") or []) != (metadata.get_all("License-File", []) or []):
            raise BundleError("Python wheel notice license-file list differs from METADATA")
        if entry.get("bundle_target") != f"third-party-notices/{entry['component']}/{source.name}":
            raise BundleError("Python wheel notice bundle target differs from its locked source")
        if _sha256(source) != entry.get("evidence_sha256"):
            raise BundleError("Python wheel notice hash differs from its locked source")
        inventory_sources.add(cache_relative)
    if inventory_sources != set(notice_sources):
        raise BundleError("Python wheel notice inventory differs from all locked runtime notices")


def _notice_files() -> list[PlannedFile]:
    """Preserve reviewed local notice material and report inventory completeness."""
    inventory = _load_json(_ROOT / "scripts/portable/third-party-notices/inventory.json")
    if inventory.get("format_version") != 1:
        raise BundleError("notice inventory format is unsupported")
    components = inventory.get("components")
    _validate_required_notice_components(components)
    files: list[PlannedFile] = []
    entries: list[dict[str, Any]] = []
    for entry in components:
        public = {key: entry[key] for key in ("component", "name", "version", "license_expr", "is_gap")}
        public["evidence_verified"] = entry.get("evidence_verified") is True
        for key in ("license_source_relative", "upstream_source", "upstream_revision", "package_metadata_source",
                    "evidence_bytes", "evidence_extraction", "browser_runtime_lock", "browser_executable_sha256",
                    "chromium_component_metadata", "empty_credit_entry_note", "distribution", "cache_relative_path",
                    "bundle_target", "metadata_license_files"):
            if key in entry:
                public[key] = entry[key]
        if not entry["is_gap"]:
            if entry.get("evidence_verified") is not True:
                raise BundleError("notice input lacks verified provenance")
            relative = _safe_relative(entry["notice_source"])
            source_key = (entry["component"], entry["version"], relative)
            reviewed_repository_digest = _REVIEWED_REPOSITORY_NOTICE_SOURCES.get(source_key)
            if not relative.startswith(".tmp/dependencies/") and reviewed_repository_digest is None:
                raise BundleError("notice input is outside the approved dependency cache")
            if reviewed_repository_digest is not None and entry.get("evidence_sha256") != reviewed_repository_digest:
                raise BundleError("reviewed repository notice does not match its pinned version and hash")
            source = _ROOT / relative
            _assert_safe_ancestors(source)
            digest = _sha256(source)
            if digest != entry.get("evidence_sha256"):
                raise BundleError("notice material differs from reviewed inventory")
            destination = _safe_relative(f"third-party-notices/{entry['component']}/{source.name}")
            files.append(PlannedFile(source, destination, source.stat().st_size, digest))
            public.update({"file": destination, "sha256": digest})
        entries.append(public)
    notice_complete = bool(entries) and all(entry["evidence_verified"] and not entry["is_gap"] for entry in entries)
    content = (json.dumps({"format_version": 1,
        "notice_complete": notice_complete, "components": entries},
        ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    files.append(PlannedFile(None, "third-party-notices/inventory.json", len(content),
        hashlib.sha256(content).hexdigest(), content=content))
    return files


def _app_version(source_root: Path) -> str:
    version_file = source_root / "src" / "version.py"
    try:
        match = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', version_file.read_text(encoding="utf-8"), re.MULTILINE)
    except (OSError, UnicodeError) as exc:
        raise BundleError("application version could not be read") from exc
    if match is None:
        raise BundleError("application version is missing")
    return match.group(1)


def _assert_disk_floor(path: Path, required_bytes: int) -> None:
    usage = shutil.disk_usage(path)
    if usage.free < _MIN_FREE_BYTES or usage.free / usage.total < _MIN_FREE_RATIO:
        raise BundleError("disk free space is below the 10 GiB or 5% safety floor")
    if usage.free - required_bytes < _MIN_FREE_BYTES or (usage.free - required_bytes) / usage.total < _MIN_FREE_RATIO:
        raise BundleError("estimated bundle staging peak would cross the disk safety floor")


def _manifest(files: list[PlannedFile], layout: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    entries = []
    for item in files:
        digest = item.sha256
        if digest is None:
            if item.source is not None:
                digest = _sha256(item.source)
            else:
                digest = hashlib.sha256(item.content if item.content is not None else _git_head_blob(str(item.head_blob))).hexdigest()
        entries.append({"path": item.destination, "size": item.size, "sha256": digest})
    return {"format_version": 1, "release_status": layout["release_status"], "current": current, "files": entries}


def plan_bundle(release_id: str, source_root: Path = _ROOT, launcher_root: Path | None = None,
                launcher_inventory: Path | None = None) -> tuple[list[PlannedFile], dict[str, Any], dict[str, Any]]:
    if not _RELEASE_ID.fullmatch(release_id):
        raise BundleError("release-id must contain only letters, numbers, dot, underscore, and hyphen")
    layout = _load_json(_LAYOUT_PATH)
    if layout.get("format_version") != 1 or layout.get("platform") != "windows-x64" or layout.get("release_status") != "preview-integration":
        raise BundleError("bundle layout contract is unsupported")
    dependency_root = _ROOT / ".tmp" / "dependencies"
    python_root = dependency_root / "portable-python" / "python-3.13.15-e67c6b779c81-windows-x64"
    browser_root = dependency_root / "portable-browser" / "chromium-1.57.0-r1200-4b4d412c65ff-win64"
    postgres_root = dependency_root / "portable-pg" / "postgresql-17.11-3-windows-x64"
    if launcher_root is None or launcher_inventory is None:
        raise BundleError("a fresh Launcher publish and its external inventory receipt are required")
    _assert_safe_ancestors(launcher_root)
    _assert_safe_ancestors(launcher_inventory)
    launcher_root = launcher_root.resolve()
    launcher_inventory = launcher_inventory.resolve()
    allowed_launcher_root = (_ROOT / "launcher" / "dist").resolve()
    if launcher_root == allowed_launcher_root or allowed_launcher_root not in launcher_root.parents:
        raise BundleError("Launcher publish input must be a child of launcher/dist")
    python_executable = python_root / "python.exe"
    if not python_executable.is_file():
        raise BundleError("verified portable Python runtime is missing")
    _run_verifier([str(python_executable), "-B", str(_ROOT / "scripts/portable/verify-python-runtime.py"), "--runtime-root", str(python_root), "--archive", str(dependency_root / "portable-python/downloads/python-3.13.15-embed-amd64.zip"), "--lock", str(_ROOT / "scripts/portable/python-runtime.lock.json"), "--requirements-lock", str(_ROOT / "scripts/portable/requirements-python.lock.txt"), "--verify-manifest"])
    _run_verifier([str(python_executable), "-B", str(_ROOT / "scripts/portable/verify-browser-runtime.py"), "--runtime-root", str(browser_root), "--archive", str(dependency_root / "portable-browser/downloads/chromium-1200-win64.zip"), "--lock", str(_ROOT / "scripts/portable/browser-runtime.lock.json"), "--verify-manifest"])
    _verify_postgres(postgres_root, dependency_root / "portable-pg/downloads/postgresql-17.11-3-windows-x64-binaries.zip", _ROOT / "scripts/portable/postgresql-win-x64.lock.json")
    launcher_files = _launcher_files(launcher_root, launcher_inventory)
    launcher_executable = launcher_root / str(layout["launcher"]["executable"])
    if not launcher_executable.is_file():
        raise BundleError("Launcher publication entrypoint is missing")
    app_version = _app_version(source_root)
    source_files = _source_files(source_root)
    source_files = [PlannedFile(item.source, item.destination, item.size,
        item.sha256 or _sha256(item.source), item.head_blob, item.content) for item in source_files]
    content_identity = hashlib.sha256(json.dumps([(f.destination, f.sha256) for f in source_files]).encode()).hexdigest()[:12]
    app_id = f"app-{app_version}-{content_identity}"
    python_id = _component_id(python_root)
    browser_id = _component_id(browser_root)
    postgres_id = _component_id(postgres_root)
    current = {
        "format_version": 1,
        "release_status": "preview-integration",
        "release_id": release_id,
        "platform": "windows-x64",
        "app": {"exact_id": app_id, "relative_dir": "app", "version": app_version, "schema_min": 1, "schema_max": 2},
        "runtime": {"exact_id": python_id, "relative_dir": "runtime"},
        "browser": {"exact_id": browser_id, "relative_dir": "browsers"},
        "postgres": {"exact_id": postgres_id, "relative_dir": "postgres"},
        "launcher": {"exact_id": _component_id(launcher_root), "relative_dir": "launcher", "executable": layout["launcher"]["executable"]},
    }
    files = [PlannedFile(item.source, f"{current['app']['relative_dir']}/{item.destination}", item.size, item.sha256, item.head_blob, item.content) for item in source_files]
    files.extend(launcher_files)
    root_entry = _root_launch_entry(launcher_executable)
    files.append(root_entry)
    files.append(PlannedFile(None, "uninstall.exe", root_entry.size, root_entry.sha256, content=root_entry.content))
    files.extend(_tree_files(python_root, current["runtime"]["relative_dir"]))
    files.extend(_tree_files(browser_root, current["browser"]["relative_dir"]))
    files.extend(_tree_files(postgres_root, current["postgres"]["relative_dir"]))
    notice_files = _notice_files()
    files.extend(notice_files)
    notice_inventory = next(item.content for item in notice_files if item.destination == "third-party-notices/inventory.json")
    if notice_inventory is None or not json.loads(notice_inventory).get("notice_complete"):
        notice = (
            "# 第三方许可核验状态\n\n"
            "此包仅供本地集成验收，并非公开发行放行。SHA-256 清单只证明文件一致性，"
            "不代表发行者签名或来源认证。\n"
        ).encode("utf-8")
        files.append(PlannedFile(None, "THIRD_PARTY_LICENSE_GAPS.md", len(notice), hashlib.sha256(notice).hexdigest(), content=notice))
    return _deduplicate(files), layout, current


def _copy(item: PlannedFile, stage: Path) -> None:
    destination = stage / _safe_relative(item.destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if item.content is not None:
        destination.write_bytes(item.content)
    elif item.source is not None:
        _assert_safe_ancestors(item.source)
        shutil.copyfile(item.source, destination)
    else:
        destination.write_bytes(_git_head_blob(str(item.head_blob)))
    if destination.stat().st_size != item.size or (item.sha256 and _sha256(destination) != item.sha256):
        raise BundleError("source changed during packaging")


def _verify_staged_archive(archive: Path, directory: Path) -> None:
    """Check ZIP membership, CRC, sizes, and hashes against the staged manifest."""
    manifest_path = directory / "bundle-manifest.json"
    current_path = directory / "current.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = {entry["path"]: (entry["size"], entry["sha256"]) for entry in manifest["files"]}
        expected.update({
            "bundle-manifest.json": (manifest_path.stat().st_size, _sha256(manifest_path)),
            "current.json": (current_path.stat().st_size, _sha256(current_path)),
        })
        with zipfile.ZipFile(archive) as package:
            entries = package.infolist()
            names = [entry.filename for entry in entries]
            if len(names) != len(set(name.casefold() for name in names)) or set(names) != set(expected):
                raise BundleError("created ZIP entries do not match the bundle manifest")
            for entry in entries:
                digest = hashlib.sha256()
                size = 0
                with package.open(entry) as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        size += len(block)
                        digest.update(block)
                if (size, digest.hexdigest()) != expected[entry.filename]:
                    raise BundleError("created ZIP failed manifest hash validation")
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, zipfile.BadZipFile,
            zipfile.LargeZipFile, RuntimeError) as exc:
        raise BundleError("created ZIP failed CRC or manifest validation") from exc


def _commit_staged_outputs(stage: Path, staged_archive: Path, output: Path, archive: Path) -> None:
    """Publish validated outputs without replacing existing targets."""
    if not _windows_commit_enabled():
        raise BundleError("portable bundle commit is supported only on Windows")
    if output.exists() or archive.exists():
        raise BundleError("bundle output appeared during staging; refusing to overwrite")
    marker_token = os.urandom(16).hex()
    marker = stage / _INCOMPLETE_MARKER
    marker.write_text(marker_token, encoding="ascii")
    stage.rename(output)
    archive_committed = False
    try:
        staged_archive.rename(archive)
        archive_committed = True
        (output / _INCOMPLETE_MARKER).unlink()
    except OSError as exc:
        # Roll back only while the ownership marker is still ours. If rollback
        # fails, scanner sees the marker as an unknown file and blocks release.
        if archive_committed:
            raise BundleError(f"release commit failed and remains quarantined at {output}") from exc
        try:
            if (output / _INCOMPLETE_MARKER).read_text(encoding="ascii") == marker_token:
                output.rename(stage)
        except OSError as rollback_error:
            raise BundleError(f"archive commit failed and directory remains quarantined at {output}") from rollback_error
        raise BundleError("archive commit failed; newly committed directory was rolled back") from exc


def _windows_commit_enabled() -> bool:
    return os.name == "nt"


def _scan_release_directory(directory: Path) -> dict[str, Any]:
    scanner_spec = importlib.util.spec_from_file_location(
        "_portable_release_scanner", Path(__file__).with_name("scan-portable-release.py")
    )
    if scanner_spec is None or scanner_spec.loader is None:
        raise BundleError("release scanner could not be loaded")
    scanner = importlib.util.module_from_spec(scanner_spec)
    scanner_spec.loader.exec_module(scanner)
    return scanner.scan(directory)


@contextmanager
def _inherited_access_staging(parent: Path):
    """Public package inputs must inherit project access, not tempfile's owner-only ACL.

    On Windows, moving a release out of a Python private TemporaryDirectory keeps
    its private ACL. Use an exclusively created ordinary directory instead; no
    credentials or instance data are allowed in this packaging stage.
    """
    _assert_safe_ancestors(parent)
    stage = parent / f"bundle-stage-{uuid.uuid4().hex}"
    try:
        stage.mkdir()  # Default mode/inherited ACL; never reuse an existing stage.
        identity = stage.stat()
    except OSError as exc:
        raise BundleError("could not create inherited-access package staging directory") from exc
    try:
        yield stage
    finally:
        # Only delete the directory created above, never a replacement or link.
        _assert_safe_tree(stage)
        current = stage.stat()
        if (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino):
            raise BundleError("package staging identity changed; preserving directory")
        try:
            shutil.rmtree(stage)
        except OSError as exc:
            raise BundleError("could not clean owned package staging directory") from exc


def build(release_id: str, *, dry_run: bool, launcher_root: Path | None = None,
          launcher_inventory: Path | None = None) -> dict[str, Any]:
    files, layout, current = plan_bundle(release_id, launcher_root=launcher_root,
                                         launcher_inventory=launcher_inventory)
    estimated_bytes = sum(item.size for item in files)
    _assert_disk_floor(_ROOT, estimated_bytes * 2 + 32 * 1024**2)
    output = _ROOT / "launcher" / "dist" / f"portable-{release_id}"
    stage_parent = _ROOT / ".tmp" / "build" / "portable-bundle"
    if output.exists() or Path(str(output)+".zip").exists() or output.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(output)):
        raise BundleError("bundle output already exists; refusing to overwrite")
    if dry_run:
        return {"dry_run": True, "estimated_bytes": estimated_bytes, "file_count": len(files), "output": str(output), "current": current, "files": [item.destination for item in files]}
    _assert_safe_ancestors(stage_parent)
    _assert_safe_ancestors(output.parent)
    stage_parent.mkdir(parents=True, exist_ok=True)
    _assert_safe_tree(stage_parent)
    with _inherited_access_staging(stage_parent) as temporary_root:
        stage = temporary_root / "release"
        stage.mkdir()
        for item in files:
            _copy(item, stage)
        (stage / "current.json").write_text(json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        staged_files = [PlannedFile(stage / item.destination, item.destination, item.size, item.sha256) for item in files]
        manifest = _manifest(staged_files, layout, current)
        (stage / "bundle-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if _scan_release_directory(stage)["status"] != "PASS":
            raise BundleError("staged release directory failed scanner validation")
        staged_archive = temporary_root / "release.zip"
        with zipfile.ZipFile(staged_archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as package:
            for file in stage.rglob("*"):
                if file.is_file():
                    package.write(file, file.relative_to(stage).as_posix())
        _verify_staged_archive(staged_archive, stage)
        archive_sha256 = _sha256(staged_archive)
        archive = Path(str(output) + ".zip")
        _commit_staged_outputs(stage, staged_archive, output, archive)
    return {"dry_run": False, "estimated_bytes": estimated_bytes, "file_count": len(files), "output": str(output), "archive":str(archive), "archive_sha256":archive_sha256, "current": current}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(
        "Build a preview-only Windows bundle. Launcher input must come from a fresh "
        "build-launcher-prototype.ps1 publish and its external inventory receipt."
    ), epilog=(
        "Create both values by running scripts/portable/build-launcher-prototype.ps1 -PythonIntegration; "
        "then pass its PUBLISH_PATH as --launcher-root and PUBLISH_INVENTORY as --launcher-inventory. "
        "Previous --launcher-root-only commands require a fresh Launcher publish and cannot reuse historical outputs."
    ))
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--launcher-root", type=Path, required=True,
                        help="Fresh Launcher publish path printed as PUBLISH_PATH")
    parser.add_argument("--launcher-inventory", type=Path, required=True,
                        help="Receipt printed as PUBLISH_INVENTORY by the fresh Launcher build")
    args = parser.parse_args(argv)
    try:
        result = build(args.release_id, dry_run=args.dry_run, launcher_root=args.launcher_root,
                       launcher_inventory=args.launcher_inventory)
    except (BundleError, OSError, zipfile.BadZipFile) as exc:
        print(f"Portable bundle build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
