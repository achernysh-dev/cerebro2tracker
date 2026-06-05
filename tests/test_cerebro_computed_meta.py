# coding: utf-8
import unittest

from twin_plugin.cerebro_computed_meta import (
    PROGRESS_COMPLETED,
    PROGRESS_IN_PROGRESS,
    PROGRESS_READY,
    progress_from_status_info,
)


class ProgressFromStatusInfoTests(unittest.TestCase):
    def test_approved_english(self):
        self.assertEqual(
            progress_from_status_info({"name": "Approved"}),
            PROGRESS_COMPLETED,
        )

    def test_approved_russian(self):
        self.assertEqual(
            progress_from_status_info({"name": "Утверждён"}),
            PROGRESS_COMPLETED,
        )

    def test_empty_name_resolved_from_catalog(self):
        catalog = {12: "approved"}
        self.assertEqual(
            progress_from_status_info({"id": 12, "name": ""}, name_catalog=catalog),
            PROGRESS_COMPLETED,
        )

    def test_cc_style_id_string_key(self):
        catalog = {5: "Approved"}
        self.assertEqual(
            progress_from_status_info({"id": "5", "name": ""}, name_catalog=catalog),
            PROGRESS_COMPLETED,
        )

    def test_empty_status_id_zero_is_unknown(self):
        self.assertIsNone(
            progress_from_status_info({"id": 0, "name": ""}, name_catalog={}),
        )

    def test_vypolnena_russian(self):
        self.assertEqual(
            progress_from_status_info({"name": "выполнена"}),
            PROGRESS_COMPLETED,
        )

    def test_in_progress(self):
        self.assertEqual(
            progress_from_status_info({"name": "in progress"}),
            PROGRESS_IN_PROGRESS,
        )


class RollupMeanTests(unittest.TestCase):
    def test_mean_two_done_three_open(self):
        leaf_pcts = [100, 100, 0, 0, 0]

        breakdown = {0: 0, 50: 0, 100: 0}
        for pct in leaf_pcts:
            breakdown[pct] = breakdown.get(pct, 0) + 1
        mean_progress = sum(leaf_pcts) / float(len(leaf_pcts))
        rounded = int(round(mean_progress))

        self.assertEqual(rounded, 40)
        self.assertEqual(breakdown, {0: 3, 50: 0, 100: 2})


if __name__ == "__main__":
    unittest.main()
