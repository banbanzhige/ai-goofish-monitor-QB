"""Program-bundle whitelist and integrity tests without copying runtimes."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import sys
import uuid


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("portable_bundle_builder", ROOT / "scripts/portable/build-portable-bundle.py")
builder = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = builder
SPEC.loader.exec_module(builder)
INVENTORY_SPEC = importlib.util.spec_from_file_location(
    "portable_launcher_inventory", ROOT / "scripts/portable/launcher_publish_inventory.py"
)
launcher_inventory = importlib.util.module_from_spec(INVENTORY_SPEC)
sys.modules[INVENTORY_SPEC.name] = launcher_inventory
INVENTORY_SPEC.loader.exec_module(launcher_inventory)


class PortableBundleTests(unittest.TestCase):
    def test_public_staging_is_exclusive_and_cleans_only_itself(self):
        parent = ROOT / ".tmp" / "tests"
        with builder._inherited_access_staging(parent) as first:
            with builder._inherited_access_staging(parent) as second:
                self.assertNotEqual(first, second)
                (first / "payload.txt").write_text("fixture", encoding="utf-8")
            self.assertFalse(second.exists())
            self.assertTrue(first.exists())
        self.assertFalse(first.exists())

    def test_public_staging_failure_cleans_owned_directory(self):
        parent = ROOT / ".tmp" / "tests"
        with self.assertRaisesRegex(RuntimeError, "injected"):
            with builder._inherited_access_staging(parent) as stage:
                raise RuntimeError("injected")
        self.assertFalse(stage.exists())

    @unittest.skipUnless(os.name == "nt", "Windows directory ACL regression")
    def test_public_staging_does_not_introduce_private_acl_after_move(self):
        # Unlike TemporaryDirectory, this fixture inherits the project's ACL.
        parent = ROOT / ".tmp" / "tests" / f"bundle-access-{uuid.uuid4().hex}"
        parent.mkdir()
        output = parent / "published"
        try:
            with builder._inherited_access_staging(parent) as stage:
                release = stage / "release"
                release.mkdir()
                release.rename(output)
            check = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                 "$ErrorActionPreference='Stop'; "
                 "$acl=([IO.DirectoryInfo]::new($env:LAUNCHER_ACL_TEST_PATH)).GetAccessControl(); "
                 "if($acl.AreAccessRulesProtected){throw 'Unexpected private ACL'}; "
                 "$rules=$acl.GetAccessRules($true,$true,[Security.Principal.SecurityIdentifier]); "
                 "if(-not @($rules | Where-Object IsInherited).Count){throw 'Missing inherited access'}; "
                 "Write-Output 'INHERITED_PACKAGE_ACCESS_PASS'"],
                env={**os.environ, "LAUNCHER_ACL_TEST_PATH": str(output)},
                capture_output=True, timeout=30,
            )
            self.assertEqual(check.returncode, 0, check.stderr.decode("utf-8", errors="replace"))
            self.assertIn(b"INHERITED_PACKAGE_ACCESS_PASS", check.stdout)
        finally:
            if output.exists():
                output.rmdir()
            parent.rmdir()

    def _fresh_launcher_fixture(self, parent):
        temporary = tempfile.TemporaryDirectory(prefix="launcher-inventory-", dir=parent)
        repository = Path(temporary.name)
        acceptance_id = "20260924-153000-0123456789ab"
        dist = repository / "launcher" / "dist"
        publish = dist / f"launcher-p1-acceptance-{acceptance_id}"
        publish.mkdir(parents=True)
        (publish / "AiGoofish.Launcher.App.exe").write_bytes(b"launcher-image")
        (publish / "AiGoofish.Launcher.App.runtimeconfig.json").write_bytes(b"{}\n")
        (publish / "nested").mkdir()
        (publish / "nested" / "runtime.dll").write_bytes(b"runtime")
        return temporary, repository, publish, acceptance_id

    def test_fresh_launcher_inventory_accepts_exact_tree(self):
        parent = ROOT / ".tmp" / "tests"
        with tempfile.TemporaryDirectory(prefix="launcher-inventory-clean-", dir=parent) as temporary:
            outer = Path(temporary)
            fixture, repository, publish, acceptance_id = self._fresh_launcher_fixture(outer)
            with fixture:
                receipt = launcher_inventory.record_inventory(repository, publish, acceptance_id)
                verified = launcher_inventory.verify_inventory(repository, publish, receipt)
                self.assertEqual([entry["path"] for entry in verified], [
                    "AiGoofish.Launcher.App.exe",
                    "AiGoofish.Launcher.App.runtimeconfig.json",
                    "nested/runtime.dll",
                ])
                self.assertFalse(receipt.is_relative_to(publish))
                self.assertFalse(receipt.read_bytes().startswith(b"\xef\xbb\xbf"))

                with patch.object(builder, "_ROOT", repository):
                    packaged = builder._launcher_files(publish, receipt)
                self.assertEqual([entry.destination for entry in packaged], [
                    "launcher/AiGoofish.Launcher.App.exe",
                    "launcher/AiGoofish.Launcher.App.runtimeconfig.json",
                    "launcher/nested/runtime.dll",
                ])

    def test_root_launch_entry_retargets_the_existing_apphost(self):
        parent = ROOT / ".tmp" / "tests" / "portable-layout-r12"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            source = Path(temporary) / "AiGoofish.Launcher.App.exe"
            source.write_bytes(b"MZ" + b"AiGoofish.Launcher.App.dll" + bytes(100))
            entry = builder._root_launch_entry(source)
            self.assertEqual(entry.destination, "AiGoofish.exe")
            self.assertIn(b"launcher\\AiGoofish.Launcher.App.dll", entry.content)
            self.assertEqual(entry.size, len(entry.content))
            self.assertEqual(entry.sha256, hashlib.sha256(entry.content).hexdigest())
            source.write_bytes(b"MZ" + b"other.dll" + bytes(100))
            with self.assertRaises(builder.BundleError):
                builder._root_launch_entry(source)

    def test_fresh_launcher_inventory_rejects_settings_and_other_added_files(self):
        parent = ROOT / ".tmp" / "tests"
        for added_name in ("settings.json", "user-attachment.bin"):
            with self.subTest(added_name=added_name), tempfile.TemporaryDirectory(prefix="launcher-inventory-extra-", dir=parent) as temporary:
                fixture, repository, publish, acceptance_id = self._fresh_launcher_fixture(Path(temporary))
                with fixture:
                    receipt = launcher_inventory.record_inventory(repository, publish, acceptance_id)
                    (publish / added_name).write_bytes(b"must not be bundled")
                    with self.assertRaisesRegex(launcher_inventory.InventoryError, "differ from the independently recorded inventory"):
                        launcher_inventory.verify_inventory(repository, publish, receipt)

    def test_fresh_launcher_inventory_rejects_changed_bytes(self):
        parent = ROOT / ".tmp" / "tests"
        with tempfile.TemporaryDirectory(prefix="launcher-inventory-changed-", dir=parent) as temporary:
            fixture, repository, publish, acceptance_id = self._fresh_launcher_fixture(Path(temporary))
            with fixture:
                receipt = launcher_inventory.record_inventory(repository, publish, acceptance_id)
                (publish / "nested" / "runtime.dll").write_bytes(b"changed")
                with self.assertRaisesRegex(launcher_inventory.InventoryError, "bytes differ"):
                    launcher_inventory.verify_inventory(repository, publish, receipt)

    def test_fresh_launcher_inventory_rejects_missing_files(self):
        parent = ROOT / ".tmp" / "tests"
        with tempfile.TemporaryDirectory(prefix="launcher-inventory-missing-file-", dir=parent) as temporary:
            fixture, repository, publish, acceptance_id = self._fresh_launcher_fixture(Path(temporary))
            with fixture:
                receipt = launcher_inventory.record_inventory(repository, publish, acceptance_id)
                (publish / "nested" / "runtime.dll").unlink()
                with self.assertRaisesRegex(launcher_inventory.InventoryError, "differ from the independently recorded inventory"):
                    launcher_inventory.verify_inventory(repository, publish, receipt)

    def test_fresh_launcher_inventory_rejects_missing_and_inconsistent_receipts(self):
        parent = ROOT / ".tmp" / "tests"
        with tempfile.TemporaryDirectory(prefix="launcher-inventory-invalid-", dir=parent) as temporary:
            fixture, repository, publish, acceptance_id = self._fresh_launcher_fixture(Path(temporary))
            with fixture:
                receipt = launcher_inventory.record_inventory(repository, publish, acceptance_id)
                receipt.unlink()
                with self.assertRaises(launcher_inventory.InventoryError):
                    launcher_inventory.verify_inventory(repository, publish, receipt)
                receipt = launcher_inventory.record_inventory(repository, publish, acceptance_id)
                payload = json.loads(receipt.read_text(encoding="utf-8"))
                payload["launcher_root"] = str(publish.parent)
                receipt.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaisesRegex(launcher_inventory.InventoryError, "different absolute root"):
                    launcher_inventory.verify_inventory(repository, publish, receipt)

    def test_fresh_launcher_inventory_rejects_path_traversal_and_duplicate_entries(self):
        parent = ROOT / ".tmp" / "tests"
        with tempfile.TemporaryDirectory(prefix="launcher-inventory-paths-", dir=parent) as temporary:
            fixture, repository, publish, acceptance_id = self._fresh_launcher_fixture(Path(temporary))
            with fixture:
                receipt = launcher_inventory.record_inventory(repository, publish, acceptance_id)
                payload = json.loads(receipt.read_text(encoding="utf-8"))
                payload["files"][0]["path"] = "../outside"
                receipt.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaisesRegex(launcher_inventory.InventoryError, "unsafe path"):
                    launcher_inventory.verify_inventory(repository, publish, receipt)

                receipt.unlink()
                receipt = launcher_inventory.record_inventory(repository, publish, acceptance_id)
                payload = json.loads(receipt.read_text(encoding="utf-8"))
                payload["files"].append(dict(payload["files"][0]))
                receipt.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaisesRegex(launcher_inventory.InventoryError, "duplicate or case-colliding"):
                    launcher_inventory.verify_inventory(repository, publish, receipt)

    def test_launcher_inventory_cannot_overwrite_bundle_metadata(self):
        entry = {"path": "bundle-manifest.json", "size": 1, "sha256": hashlib.sha256(b"x").hexdigest()}
        with patch.object(builder._LAUNCHER_INVENTORY, "verify_inventory", return_value=[entry]):
            with self.assertRaisesRegex(builder.BundleError, "collides with bundle metadata"):
                builder._launcher_files(ROOT / "launcher/dist/fixture", ROOT / ".tmp/receipt.json")

    def test_zip_write_failure_does_not_publish_directory(self):
        parent = ROOT / ".tmp" / "tests"
        with tempfile.TemporaryDirectory(prefix="portable-release-zip-write-", dir=parent) as temporary:
            fixture = Path(temporary)
            (fixture / "launcher" / "dist").mkdir(parents=True)
            files = [builder.PlannedFile(None, "app/payload.bin", 7,
                hashlib.sha256(b"payload").hexdigest(), content=b"payload")]
            with patch.multiple(builder, _ROOT=fixture,
                plan_bundle=lambda *_args, **_kwargs: (files, {"release_status": "preview-integration"}, {"format_version": 1}),
                _assert_disk_floor=lambda *_args: None, _scan_release_directory=lambda _path: {"status": "PASS"},
                _windows_commit_enabled=lambda: True), \
                 patch.object(builder.zipfile.ZipFile, "write", side_effect=OSError("injected ZIP write failure")):
                with self.assertRaises(OSError):
                    builder.build("zip-failure", dry_run=False)
            self.assertFalse((fixture / "launcher" / "dist" / "portable-zip-failure").exists())
            self.assertFalse((fixture / "launcher" / "dist" / "portable-zip-failure.zip").exists())

    def test_crc_validation_failure_does_not_publish_directory(self):
        parent = ROOT / ".tmp" / "tests"
        with tempfile.TemporaryDirectory(prefix="portable-release-crc-", dir=parent) as temporary:
            fixture = Path(temporary)
            (fixture / "launcher" / "dist").mkdir(parents=True)
            files = [builder.PlannedFile(None, "app/payload.bin", 7,
                hashlib.sha256(b"payload").hexdigest(), content=b"payload")]
            original_verify = builder._verify_staged_archive
            def corrupt_crc(archive, stage):
                with builder.zipfile.ZipFile(archive) as package:
                    payload = next(info for info in package.infolist() if info.filename == "app/payload.bin")
                raw = bytearray(archive.read_bytes())
                cursor = 0
                while True:
                    cursor = raw.find(b"PK\x01\x02", cursor)
                    if cursor < 0:
                        raise AssertionError("ZIP central directory entry not found")
                    name_length, extra_length, comment_length = struct.unpack_from("<HHH", raw, cursor + 28)
                    name = bytes(raw[cursor + 46:cursor + 46 + name_length]).decode("utf-8")
                    if name == payload.filename:
                        crc = struct.unpack_from("<I", raw, cursor + 16)[0]
                        struct.pack_into("<I", raw, cursor + 16, crc ^ 1)
                        archive.write_bytes(raw)
                        break
                    cursor += 46 + name_length + extra_length + comment_length
                original_verify(archive, stage)
            with patch.multiple(builder, _ROOT=fixture,
                plan_bundle=lambda *_args, **_kwargs: (files, {"release_status": "preview-integration"}, {"format_version": 1}),
                _assert_disk_floor=lambda *_args: None, _scan_release_directory=lambda _path: {"status": "PASS"},
                _windows_commit_enabled=lambda: True), \
                 patch.object(builder, "_verify_staged_archive", side_effect=corrupt_crc):
                with self.assertRaisesRegex(builder.BundleError, "CRC or manifest validation"):
                    builder.build("crc-failure", dry_run=False)
            self.assertFalse((fixture / "launcher" / "dist" / "portable-crc-failure").exists())
            self.assertFalse((fixture / "launcher" / "dist" / "portable-crc-failure.zip").exists())

    def test_archive_commit_failure_rolls_back_owned_directory(self):
        parent = ROOT / ".tmp" / "tests"
        with tempfile.TemporaryDirectory(prefix="portable-release-commit-", dir=parent) as temporary:
            fixture = Path(temporary)
            (fixture / "launcher" / "dist").mkdir(parents=True)
            files = [builder.PlannedFile(None, "app/payload.bin", 7,
                hashlib.sha256(b"payload").hexdigest(), content=b"payload")]
            original_rename = Path.rename
            def fail_archive_rename(path, target):
                if path.name == "release.zip":
                    raise OSError("injected archive commit failure")
                return original_rename(path, target)
            with patch.multiple(builder, _ROOT=fixture,
                plan_bundle=lambda *_args, **_kwargs: (files, {"release_status": "preview-integration"}, {"format_version": 1}),
                _assert_disk_floor=lambda *_args: None, _scan_release_directory=lambda _path: {"status": "PASS"},
                _windows_commit_enabled=lambda: True), \
                 patch.object(Path, "rename", fail_archive_rename):
                with self.assertRaisesRegex(builder.BundleError, "rolled back"):
                    builder.build("commit-failure", dry_run=False)
            self.assertFalse((fixture / "launcher" / "dist" / "portable-commit-failure").exists())
            self.assertFalse((fixture / "launcher" / "dist" / "portable-commit-failure.zip").exists())

    def test_concurrent_final_target_is_not_overwritten(self):
        parent = ROOT / ".tmp" / "tests"
        with tempfile.TemporaryDirectory(prefix="portable-release-race-", dir=parent) as temporary:
            fixture = Path(temporary)
            (fixture / "launcher" / "dist").mkdir(parents=True)
            files = [builder.PlannedFile(None, "app/payload.bin", 7,
                hashlib.sha256(b"payload").hexdigest(), content=b"payload")]
            original_verify = builder._verify_staged_archive
            def create_competing_target(archive, stage):
                original_verify(archive, stage)
                concurrent = fixture / "launcher" / "dist" / "portable-race"
                concurrent.mkdir()
                (concurrent / "owned-by-other-process.txt").write_text("preserve", encoding="utf-8")
            with patch.multiple(builder, _ROOT=fixture,
                plan_bundle=lambda *_args, **_kwargs: (files, {"release_status": "preview-integration"}, {"format_version": 1}),
                _assert_disk_floor=lambda *_args: None, _scan_release_directory=lambda _path: {"status": "PASS"},
                _windows_commit_enabled=lambda: True), \
                 patch.object(builder, "_verify_staged_archive", side_effect=create_competing_target):
                with self.assertRaisesRegex(builder.BundleError, "appeared during staging"):
                    builder.build("race", dry_run=False)
            self.assertEqual((fixture / "launcher" / "dist" / "portable-race" / "owned-by-other-process.txt").read_text(encoding="utf-8"), "preserve")

    def test_repeated_release_id_refuses_existing_directory_and_zip(self):
        parent = ROOT / ".tmp" / "tests"
        with tempfile.TemporaryDirectory(prefix="portable-release-repeat-", dir=parent) as temporary:
            fixture = Path(temporary)
            output = fixture / "launcher" / "dist" / "portable-repeat"
            output.mkdir(parents=True)
            (output / "sentinel.txt").write_text("preserve", encoding="utf-8")
            archive = Path(str(output) + ".zip")
            archive.write_bytes(b"existing archive")
            files = []
            with patch.multiple(builder, _ROOT=fixture,
                plan_bundle=lambda *_args, **_kwargs: (files, {"release_status": "preview-integration"}, {"format_version": 1}),
                _assert_disk_floor=lambda *_args: None):
                with self.assertRaisesRegex(builder.BundleError, "already exists"):
                    builder.build("repeat", dry_run=False)
            self.assertEqual((output / "sentinel.txt").read_text(encoding="utf-8"), "preserve")
            self.assertEqual(archive.read_bytes(), b"existing archive")

    def test_windows_unsafe_names_and_case_collisions_rejected(self):
        for value in ("../outside", "C:/outside", "file:stream", "folder/file.", "folder/name?", "/outside", "CON.txt", "a/NUL", "a//b", "a/./b", "a\\b", "a/line\nname", "LPT¹.txt"):
            with self.assertRaises(builder.BundleError):
                builder._safe_relative(value)
        with self.assertRaises(builder.BundleError):
            builder._deduplicate([builder.PlannedFile(None,"app/A.py",0),builder.PlannedFile(None,"app/a.py",0)])

    def test_source_scope_excludes_real_data_and_has_fixed_defaults(self):
        files = builder._source_files(ROOT)
        paths = {item.destination for item in files}
        self.assertIn("scripts/portable/python-bootstrap.py", paths)
        self.assertIn("src/log_retention.py", paths)
        self.assertNotIn("src/storage/server_migration.py", paths)
        for path in ("src/account_policy.py", "src/web/account_models.py", "static/js/account_policy.js"):
            self.assertIn(path, paths)
        self.assertIn("License", paths)
        self.assertIn("defaults/prompts/base_prompt.txt", paths)
        self.assertIn("defaults/prompts/bayes/bayes_v1.json", paths)
        self.assertFalse(any(path.startswith(("state/","logs/","jsonl/","static/avatars/","images/Example/")) for path in paths))
        self.assertFalse(any(Path(path).name in {".env","config.json"} for path in paths))
        self.assertNotIn("prompts/base_prompt.txt", paths)

    def test_unreviewed_source_asset_is_rejected(self):
        parent = ROOT / ".tmp" / "tests"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="source-allowlist-", dir=parent) as temporary:
            root = Path(temporary)
            for relative in builder._SOURCE_ENTRYPOINTS:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"entrypoint")
            (root / "src").mkdir(parents=True, exist_ok=True)
            for relative in ("images/login-bg.png", "images/logo/favicon 32x32.png",
                             "images/logo/logo 128x128.png", "images/logo/logo 2048x2048.png",
                             "images/logo/banner.png", *builder._GUIDES):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"asset")
            (root / "src" / "000_unreviewed.py").write_bytes(b"unreviewed")
            completed = type("Completed", (), {"stdout": b""})()
            with patch.object(builder.subprocess, "run", return_value=completed), \
                 patch.object(builder, "_git_head_blob", return_value=b"default"):
                with self.assertRaisesRegex(builder.BundleError, "untracked program asset"):
                    builder._source_files(root)

    def test_copy_verifies_hash_against_planned_content(self):
        parent = ROOT / ".tmp/tests/portable-bundle"
        parent.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(dir=parent) as temporary:
                root = Path(temporary)
                source = root / "source.py"
                source.write_bytes(b"original")
                planned = builder.PlannedFile(source,"app/file.py",8,hashlib.sha256(b"original").hexdigest())
                source.write_bytes(b"modified")
                with self.assertRaises(builder.BundleError):
                    builder._copy(planned, root / "stage")
        finally:
            parent.rmdir()

    def test_projected_peak_must_preserve_low_disk_floor(self):
        with patch.object(builder.shutil, "disk_usage", return_value=type("Disk",(),{"free":51*1024**3,"total":1000*1024**3})()):
            with self.assertRaises(builder.BundleError):
                builder._assert_disk_floor(ROOT, 2*1024**3)

    def test_notice_inputs_are_copied_with_hashes_and_complete_set_is_reported(self):
        files = builder._notice_files()
        paths = {item.destination for item in files}
        self.assertIn("third-party-notices/dotnet-runtime-license/LICENSE.TXT", paths)
        self.assertIn("third-party-notices/avalonia-ui/avalonia-MIT.txt", paths)
        chromium_credits = "third-party-notices/chromium/chromium-143-r1200-credits.html"
        onnx_license = "third-party-notices/chromium-onnxruntime-headers/onnxruntime-headers-v1.23.0-MIT.txt"
        self.assertIn(chromium_credits, paths)
        self.assertIn(onnx_license, paths)
        self.assertTrue(all(item.sha256 for item in files))
        inventory = next(item for item in files if item.destination.endswith("/inventory.json"))
        parsed = json.loads(inventory.content)
        self.assertTrue(parsed["notice_complete"])
        source_inventory = json.loads((ROOT / "scripts/portable/third-party-notices/inventory.json").read_text(encoding="utf-8"))
        wheel_entries = [item for item in source_inventory["components"] if item.get("component", "").startswith("python-wheel-")]
        self.assertEqual(len(wheel_entries), 93)
        self.assertNotIn("python-locked-wheels", {item["component"] for item in source_inventory["components"]})
        self.assertNotIn("python-locked-wheels", {item["component"] for item in parsed["components"] if item["is_gap"]})

        site_packages = ROOT / ".tmp/dependencies/portable-python/python-3.13.15-e67c6b779c81-windows-x64/site-packages"
        cache_paths = [item["cache_relative_path"] for item in wheel_entries]
        self.assertEqual(len(set(cache_paths)), 93)
        planned_by_destination = {item.destination: item for item in files}
        pins = {
            re.sub(r"[-_.]+", "-", match.group(1)).lower(): match.group(2)
            for match in re.finditer(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)", (ROOT / "scripts/portable/requirements-python.lock.txt").read_text(encoding="utf-8"), re.MULTILINE)
        }
        notice_name = re.compile(r"(?i)(license|licence|notice|copying|copyright|patent)")
        cached_notice_paths = {
            path.relative_to(site_packages).as_posix()
            for path in site_packages.glob("*.dist-info/**")
            if path.is_file() and notice_name.search(path.name)
        }
        self.assertEqual(set(cache_paths), cached_notice_paths)
        wheel_versions = {}
        for entry in wheel_entries:
            self.assertFalse(entry["is_gap"])
            self.assertRegex(entry["evidence_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(entry["cache_relative_path"], entry["license_source_relative"].removeprefix("site-packages/"))
            self.assertTrue(entry["notice_source"].endswith("/site-packages/" + entry["cache_relative_path"]))
            source = site_packages / Path(entry["cache_relative_path"])
            self.assertTrue(source.is_file(), entry["cache_relative_path"])
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            self.assertEqual(entry["evidence_sha256"], digest, entry["cache_relative_path"])
            expected_target = f"third-party-notices/{entry['component']}/{source.name}"
            self.assertEqual(entry["bundle_target"], expected_target)
            self.assertIn(expected_target, planned_by_destination)
            self.assertEqual(planned_by_destination[expected_target].sha256, digest)
            normalized_name = re.sub(r"[-_.]+", "-", entry["distribution"]).lower()
            self.assertIn(normalized_name, pins)
            self.assertEqual(entry["version"], pins[normalized_name])
            wheel_versions[normalized_name] = entry["version"]

        self.assertEqual(len(wheel_versions), 60)
        self.assertEqual(wheel_versions, pins)
        for dist_info in site_packages.glob("*.dist-info"):
            metadata_text = (dist_info / "METADATA").read_text(encoding="utf-8")
            distribution = re.search(r"^Name: (.+)$", metadata_text, re.MULTILINE).group(1)
            version = re.search(r"^Version: (.+)$", metadata_text, re.MULTILINE).group(1)
            normalized_name = re.sub(r"[-_.]+", "-", distribution).lower()
            self.assertEqual(version, pins[normalized_name])
            records = [entry for entry in wheel_entries if entry["distribution"] == distribution]
            self.assertTrue(records, distribution)
            expected_refs = re.findall(r"^License-File: (.+)$", metadata_text, re.MULTILINE)
            self.assertTrue(all(record["metadata_license_files"] == expected_refs for record in records), distribution)
            for reference in expected_refs:
                self.assertTrue((dist_info / "licenses" / reference).is_file() or (dist_info / reference).is_file(), f"{distribution}: {reference}")
        copied_wheel_notices = {path for path in paths if path.startswith("third-party-notices/python-wheel-")}
        self.assertEqual(len(copied_wheel_notices), 93)
        self.assertEqual(copied_wheel_notices, {entry["bundle_target"] for entry in wheel_entries})
        unresolved = {item["component"] for item in parsed["components"] if item["is_gap"]}
        self.assertNotIn("avalonia-ui", unresolved)
        self.assertEqual(unresolved, set())
        self.assertEqual(next(item for item in files if item.destination == chromium_credits).sha256,
                         "baac582df59212838afdd377fd757412e79d3865d7ff2e7c2b9f898e6513cd6b")
        self.assertEqual(next(item for item in files if item.destination == onnx_license).sha256,
                         "2f07c72751aed99790b8a4869cf2311df85a860b22ded05fa22803587a48922c")
        chromium_record = next(item for item in parsed["components"] if item["component"] == "chromium")
        self.assertEqual(chromium_record["browser_executable_sha256"],
                         "98da1bd10d317fd533c357dfcb374bb9c8c23d28c11c0a04bbd550d2add95e2d")
        self.assertIn("560 div.license pre", chromium_record["evidence_extraction"])
        self.assertIn("empty license block", chromium_record["empty_credit_entry_note"])
        onnx_record = next(item for item in parsed["components"] if item["component"] == "chromium-onnxruntime-headers")
        self.assertEqual(onnx_record["upstream_revision"], "be835efc56aca19b8e810538ec93c8e150e0fc61")
        avalonia_notice = next(item for item in files if item.destination == "third-party-notices/avalonia-ui/avalonia-MIT.txt")
        self.assertEqual(avalonia_notice.sha256, "213814d306090074d234d760239ff0f67eb9b8d20eefb4d5631bb39dbe0b769b")

    def test_chromium_credits_snapshot_is_full_and_preserves_the_upstream_empty_entry(self):
        path = ROOT / "scripts/portable/third-party-notices/chromium-143-r1200-credits.html"
        raw = path.read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
        html = raw.decode("utf-8")
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         "baac582df59212838afdd377fd757412e79d3865d7ff2e7c2b9f898e6513cd6b")
        blocks = re.findall(r'<div class="license">\s*<pre>(.*?)</pre>\s*</div>', html, flags=re.DOTALL)
        self.assertEqual(len(blocks), 560)
        self.assertEqual(sum(bool(block.strip()) for block in blocks), 559)
        empty_entry = re.search(
            r'<div class="product">\s*<span class="title">Headers for ONNX Runtime C/C\+\+ APIs</span>.*?'
            r'<div class="license">\s*<pre></pre>\s*</div>', html, flags=re.DOTALL)
        self.assertIsNotNone(empty_entry)
        for pattern in (r'\b[A-Z]:\\(?:Users|Windows|ProgramData)\\', r'file://', r'user-data-dir',
                        r'cookie\s*=', r'authorization\s*:\s*bearer\s+[A-Za-z0-9._~-]{16,}', r'localhost|127\.0\.0\.1'):
            self.assertNotRegex(html, pattern)

    def test_any_unresolved_notice_prevents_complete_inventory(self):
        source_inventory = json.loads((ROOT / "scripts/portable/third-party-notices/inventory.json").read_text(encoding="utf-8"))
        candidate = json.loads(json.dumps(source_inventory))
        chromium = next(item for item in candidate["components"] if item["component"] == "chromium")
        chromium["is_gap"] = True
        with patch.object(builder, "_load_json", return_value=candidate):
            files = builder._notice_files()
        parsed = json.loads(next(item for item in files if item.destination.endswith("/inventory.json")).content)
        self.assertFalse(parsed["notice_complete"])

    def test_missing_required_notice_rows_fail_closed(self):
        inventory_path = ROOT / "scripts/portable/third-party-notices/inventory.json"
        source_inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        for removed in (
            {"chromium"},
            {"chromium-onnxruntime-headers"},
            {"chromium", "chromium-onnxruntime-headers"},
            {"postgresql"},
        ):
            candidate = json.loads(json.dumps(source_inventory))
            candidate["components"] = [entry for entry in candidate["components"] if entry["component"] not in removed]
            with self.subTest(removed=removed), patch.object(builder, "_load_json", return_value=candidate):
                with self.assertRaises(builder.BundleError):
                    builder._notice_files()

        candidate = json.loads(json.dumps(source_inventory))
        wheel_row = next(entry for entry in candidate["components"] if entry["component"].startswith("python-wheel-"))
        candidate["components"].remove(wheel_row)
        with patch.object(builder, "_load_json", return_value=candidate):
            with self.assertRaises(builder.BundleError):
                builder._notice_files()

    def test_duplicate_required_notice_row_fails_closed(self):
        inventory_path = ROOT / "scripts/portable/third-party-notices/inventory.json"
        candidate = json.loads(inventory_path.read_text(encoding="utf-8"))
        chromium = next(entry for entry in candidate["components"] if entry["component"] == "chromium")
        candidate["components"].append(dict(chromium))
        with patch.object(builder, "_load_json", return_value=candidate):
            with self.assertRaises(builder.BundleError):
                builder._notice_files()

    def test_bundle_gap_marker_tracks_notice_completeness(self):
        inventory_path = ROOT / "scripts/portable/third-party-notices/inventory.json"
        original_load_json = builder._load_json
        source_inventory = original_load_json(inventory_path)
        launcher_root = ROOT / "launcher/dist/portable-acceptance-frozen-20260923-p1"

        def plan_for(candidate):
            def load_json(path):
                if Path(path) == inventory_path:
                    return candidate
                return original_load_json(path)

            with patch.object(builder, "_load_json", side_effect=load_json), \
                 patch.object(builder, "_run_verifier"), \
                 patch.object(builder, "_verify_postgres"), \
                 patch.object(builder, "_source_files", return_value=[]), \
                 patch.object(builder, "_launcher_files", return_value=[]), \
                 patch.object(builder, "_tree_files", return_value=[]), \
                 patch.object(builder, "_component_id", return_value="fixture"):
                planned, _, _ = builder.plan_bundle("notice-test", launcher_root=launcher_root,
                    launcher_inventory=launcher_root / "launcher-publish-inventory.json")
            return {item.destination for item in planned}

        complete_paths = plan_for(source_inventory)
        self.assertNotIn("THIRD_PARTY_LICENSE_GAPS.md", complete_paths)
        with_gap = json.loads(json.dumps(source_inventory))
        chromium = next(item for item in with_gap["components"] if item["component"] == "chromium")
        chromium["is_gap"] = True
        incomplete_paths = plan_for(with_gap)
        self.assertIn("THIRD_PARTY_LICENSE_GAPS.md", incomplete_paths)

    def test_repository_notice_source_is_pinned_to_component_version_and_hash(self):
        source_inventory = json.loads((ROOT / "scripts/portable/third-party-notices/inventory.json").read_text(encoding="utf-8"))
        cases = (
            ("avalonia-ui", "version", "12.1.3"),
            ("avalonia-ui", "notice_source", "scripts/portable/third-party-notices/another.txt"),
            ("avalonia-ui", "evidence_sha256", "0" * 64),
            ("chromium", "version", "143 / r1201"),
            ("chromium", "notice_source", "scripts/portable/third-party-notices/another.html"),
            ("chromium", "evidence_sha256", "0" * 64),
            ("chromium-onnxruntime-headers", "version", "v1.23.1"),
            ("chromium-onnxruntime-headers", "notice_source", "scripts/portable/third-party-notices/another.txt"),
            ("chromium-onnxruntime-headers", "evidence_sha256", "0" * 64),
        )
        for component, field, invalid_value in cases:
            candidate = json.loads(json.dumps(source_inventory))
            entry = next(item for item in candidate["components"] if item["component"] == component)
            entry[field] = invalid_value
            with self.subTest(component=component, field=field), patch.object(builder, "_load_json", return_value=candidate):
                with self.assertRaises(builder.BundleError):
                    builder._notice_files()
