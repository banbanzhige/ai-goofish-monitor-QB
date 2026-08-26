import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.notifier import _notifier_build_overrides
from src.notifier.channels import _ntfy_publish_target
from src.notifier.config import config, migrate_legacy_ntfy_config, parse_legacy_ntfy_url
from src.web.settings_manager import _prepare_notification_settings_update
from src.web.user_manager import (
    _clear_reused_ntfy_token_on_server_change,
    _normalize_legacy_ntfy_config_item,
)


class NtfyCompatibilityTests(unittest.TestCase):
    def test_legacy_url_preserves_ipv6_and_reverse_proxy_path(self):
        self.assertEqual(
            parse_legacy_ntfy_url("http://[::1]:8080/topic"),
            ("http://[::1]:8080", "topic", ""),
        )
        self.assertEqual(
            parse_legacy_ntfy_url("https://host.test/ntfy/topic"),
            ("https://host.test/ntfy", "topic", ""),
        )
        self.assertEqual(
            parse_legacy_ntfy_url('"https://host.test/topic"'),
            ("https://host.test", "topic", ""),
        )

    def test_old_database_config_is_normalized_for_runtime_and_ui(self):
        item = {
            "id": "1",
            "channel_type": "ntfy",
            "config": {"topic_url": "https://:tk_old@host.test/ntfy/topic"},
        }
        normalized = _normalize_legacy_ntfy_config_item(item)
        overrides = _notifier_build_overrides("ntfy", item["config"])

        self.assertEqual(normalized["config"]["topic"], "topic")
        self.assertEqual(normalized["config"]["server_url"], "https://host.test/ntfy")
        self.assertEqual(overrides["NTFY_TOKEN"], "tk_old")

    def test_local_server_change_does_not_reuse_old_token(self):
        env = {"NTFY_SERVER_URL": "https://a.test", "NTFY_TOKEN": "tk_old"}
        with patch.dict(os.environ, env, clear=False):
            changed = _prepare_notification_settings_update(
                {
                    "NTFY_TOPIC": "topic",
                    "NTFY_SERVER_URL": "https://b.test",
                    "NTFY_TOKEN": "",
                }
            )
            same_server = _prepare_notification_settings_update(
                {
                    "NTFY_TOPIC": "other",
                    "NTFY_SERVER_URL": "https://a.test",
                    "NTFY_TOKEN": "",
                }
            )

        self.assertEqual(changed["NTFY_TOKEN"], "")
        self.assertEqual(same_server["NTFY_TOKEN"], "tk_old")

    def test_database_server_change_drops_unchanged_token(self):
        existing = {
            "channel_type": "ntfy",
            "config": {"topic": "old", "server_url": "https://a.test", "token": "tk_old"},
        }
        changed = _clear_reused_ntfy_token_on_server_change(
            existing,
            {"config": {"topic": "old", "server_url": "https://b.test", "token": "tk_old"}},
        )

        self.assertNotIn("token", changed["config"])

    def test_migration_handles_quoted_url_and_keeps_utf8(self):
        original_directory = os.getcwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                Path(".env").write_text(
                    'NTFY_TOPIC_URL="https://:tk_old@old.test:8443/ntfy/topic"\n'
                    "NTFY_ENABLED=True\nOTHER=保留\n",
                    encoding="utf-8",
                )
                self.assertTrue(migrate_legacy_ntfy_config())
                raw = Path(".env").read_bytes()
                content = raw.decode("utf-8")
                config.reload()

                self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
                self.assertNotIn("NTFY_TOPIC_URL=", content)
                self.assertIn("NTFY_SERVER_URL=https://old.test:8443/ntfy", content)
                self.assertEqual(
                    _ntfy_publish_target(),
                    ("https://old.test:8443/ntfy/topic", "tk_old"),
                )
            finally:
                os.chdir(original_directory)


if __name__ == "__main__":
    unittest.main()
