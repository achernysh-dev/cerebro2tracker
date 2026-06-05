# coding: utf-8
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from twin_plugin import sync_settings
from twin_plugin.status_map import (
    DEFAULT_CEREBRO_STATUS_TO_TRACKER_KEY,
    cerebro_status_to_tracker_key,
)


class CerebroStatusToTrackerKeyTests(unittest.TestCase):
    def test_russian_selected_for_dev(self):
        self.assertEqual(
            cerebro_status_to_tracker_key({"name": "Будем делать"}),
            "selectedForDev",
        )

    def test_substring_match(self):
        self.assertEqual(
            cerebro_status_to_tracker_key({"name": "Task: in progress (dev)"}),
            "inProgress",
        )

    def test_custom_map_override(self):
        custom = dict(DEFAULT_CEREBRO_STATUS_TO_TRACKER_KEY)
        custom["будем делать"] = "open"
        self.assertEqual(
            cerebro_status_to_tracker_key({"name": "Будем делать"}, custom),
            "open",
        )

    def test_unmapped_returns_none(self):
        self.assertIsNone(
            cerebro_status_to_tracker_key({"name": "Totally Unknown Status"}),
        )


class StatusMapSettingsTests(unittest.TestCase):
    def test_normalize_status_map_keys(self):
        raw = {"  Будем делать  ": "selectedForDev", "IN_PROGRESS": "inProgress"}
        normalized = sync_settings.normalize_status_map(raw)
        self.assertEqual(normalized["будем делать"], "selectedForDev")
        self.assertEqual(normalized["in progress"], "inProgress")

    def test_load_status_map_merges_file_and_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            map_path = os.path.join(tmp, "status_map.json")
            with open(map_path, "w", encoding="utf-8") as fh:
                json.dump({"будем делать": "open"}, fh)

            settings = {"status_map": {"custom status": "testing"}}
            with patch.object(sync_settings, "get_status_map_path", return_value=map_path):
                merged = sync_settings.load_status_map(settings)

            self.assertEqual(merged["будем делать"], "open")
            self.assertEqual(merged["custom status"], "testing")
            self.assertEqual(merged["open"], "open")

    def test_config_paths(self):
        package_dir = sync_settings.get_package_dir()
        settings_dir = sync_settings.get_legacy_settings_dir()
        self.assertTrue(
            sync_settings.get_settings_path().startswith(settings_dir)
        )
        self.assertFalse(
            sync_settings.get_settings_path().startswith(package_dir)
        )
        self.assertTrue(
            sync_settings.get_status_map_path().startswith(package_dir)
        )

    def test_migrate_package_settings_into_appdata(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings_dir = os.path.join(tmp, "appdata")
            package_dir = os.path.join(tmp, "package")
            os.makedirs(settings_dir)
            os.makedirs(package_dir)
            appdata_settings = os.path.join(settings_dir, "sync_settings.json")
            package_settings = os.path.join(package_dir, "sync_settings.json")
            with open(package_settings, "w", encoding="utf-8") as fh:
                json.dump({"tracker_token": "secret", "task_map": {}}, fh)

            with patch.object(sync_settings, "get_legacy_settings_dir", return_value=settings_dir):
                with patch.object(sync_settings, "get_package_dir", return_value=package_dir):
                    migrated = sync_settings._migrate_package_settings()

            self.assertTrue(migrated)
            with open(appdata_settings, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(data["tracker_token"], "secret")

    def test_ensure_status_map_file_creates_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            map_path = os.path.join(tmp, "status_map.json")
            with patch.object(sync_settings, "get_status_map_path", return_value=map_path):
                created = sync_settings.ensure_status_map_file()

            self.assertEqual(created, map_path)
            self.assertTrue(os.path.isfile(map_path))
            with open(map_path, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(data["будем делать"], "selectedForDev")
            self.assertGreater(len(data), 50)


if __name__ == "__main__":
    unittest.main()
