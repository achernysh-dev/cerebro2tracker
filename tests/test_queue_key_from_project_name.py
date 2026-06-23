# coding: utf-8
import unittest

from twin_plugin.sync_engine import (
    queue_key_from_project_name,
    queue_name_from_project_name,
    transliterate_cyrillic_to_latin,
)


class QueueKeyFromProjectNameTests(unittest.TestCase):
    def test_cyrillic_projects_get_distinct_keys(self):
        names = ("Окко Буббоко", "Авито Штрафы", "ГПБ Корзина")
        keys = [queue_key_from_project_name(name) for name in names]
        self.assertEqual(len(set(keys)), 3)
        self.assertNotIn("CBRO", keys)

    def test_transliteration_examples(self):
        self.assertEqual(
            transliterate_cyrillic_to_latin("Окко Буббоко"), "Okko Bubboko"
        )
        self.assertEqual(queue_key_from_project_name("Окко Буббоко"), "OKKOBUBBOKO")
        self.assertEqual(queue_key_from_project_name("Авито Штрафы"), "AVITOSHTRAFY")
        self.assertEqual(queue_key_from_project_name("ГПБ Корзина"), "GPBKORZINA")

    def test_latin_name_unchanged(self):
        self.assertEqual(queue_key_from_project_name("Cerebro Test"), "CEREBROTEST")

    def test_queue_name_uses_latin_when_cyrillic(self):
        self.assertEqual(
            queue_name_from_project_name("Авито Штрафы"), "Avito Shtrafy Queue"
        )
        self.assertEqual(
            queue_name_from_project_name("Cerebro Test"), "Cerebro Test Queue"
        )


if __name__ == "__main__":
    unittest.main()
