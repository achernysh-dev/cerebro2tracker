# coding: utf-8
import unittest

from twin_plugin.sync_engine import CEREBRO_QUEUE_KEY, CEREBRO_QUEUE_NAME


class CerebroQueueConstantsTests(unittest.TestCase):
    def test_shared_queue_identity(self):
        self.assertEqual(CEREBRO_QUEUE_KEY, "CEBRO")
        self.assertEqual(CEREBRO_QUEUE_NAME, "Cerebro_queue")
        self.assertLessEqual(len(CEREBRO_QUEUE_KEY), 15)
        self.assertTrue(CEREBRO_QUEUE_KEY.isalpha())


if __name__ == "__main__":
    unittest.main()
