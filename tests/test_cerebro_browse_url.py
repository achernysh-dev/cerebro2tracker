# coding: utf-8
import importlib
import unittest

from twin_plugin import sync_settings

_sync_engine = None
_sync_engine_error = None
try:
    _sync_engine = importlib.import_module("twin_plugin.sync_engine")
except ImportError as ex:
    _sync_engine_error = ex


@unittest.skipIf(_sync_engine is None, "sync_engine unavailable: %s" % _sync_engine_error)
class CerebroBrowseUrlTests(unittest.TestCase):
    def test_browse_url_mask(self):
        url = _sync_engine.cerebro_browse_url("12345", 104)
        self.assertEqual(
            url,
            "https://apps.cerebrohq.com/app/browse/12345-104?tid=12345-104&app=desktop",
        )

    def test_issue_description_includes_markdown_link(self):
        desc = _sync_engine._issue_description(
            "12345",
            "Project / Branch",
            tracker_url="https://tracker.yandex.ru/CEBRO-1",
            server_id=104,
        )
        lines = desc.split("\n")
        self.assertEqual(lines[0], "Synced from Cerebro.")
        self.assertEqual(lines[1], "cerebro_task_id:12345")
        self.assertEqual(lines[2], "cerebro_path:Project / Branch")
        self.assertEqual(
            lines[3],
            "Cerebro: [Open in Cerebro](https://apps.cerebrohq.com/app/browse/12345-104?tid=12345-104&app=desktop)",
        )
        self.assertEqual(lines[4], "Tracker: https://tracker.yandex.ru/CEBRO-1")

    def test_issue_description_without_tracker_url(self):
        desc = _sync_engine._issue_description("99", "Path", server_id=200)
        self.assertIn("cerebro_path:Path", desc)
        self.assertIn("99-200", desc)
        self.assertNotIn("Tracker:", desc)


class CerebroServerIdSettingsTests(unittest.TestCase):
    def test_default_server_id(self):
        self.assertEqual(sync_settings.cerebro_server_id({}), 104)
        self.assertEqual(sync_settings.cerebro_server_id({"cerebro_server_id": ""}), 104)

    def test_parsed_server_id(self):
        self.assertEqual(
            sync_settings.cerebro_server_id({"cerebro_server_id": "200"}), 200
        )

    def test_invalid_server_id_falls_back(self):
        self.assertEqual(
            sync_settings.cerebro_server_id({"cerebro_server_id": "abc"}), 104
        )
        self.assertEqual(
            sync_settings.cerebro_server_id({"cerebro_server_id": "0"}), 104
        )

    def test_normalize_storage(self):
        self.assertEqual(sync_settings.normalize_cerebro_server_id(None), "104")
        self.assertEqual(sync_settings.normalize_cerebro_server_id(" 42 "), "42")


if __name__ == "__main__":
    unittest.main()
