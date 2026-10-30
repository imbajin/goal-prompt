"""Source-label redaction must not depend on adjacent text being Latin."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('business', Path(__file__).with_name('rejudge-business-state.py'))
business = importlib.util.module_from_spec(spec)
spec.loader.exec_module(business)


class BusinessRedaction(unittest.TestCase):
    def test_cjk_adjacent_labels_are_removed_without_business_loss(self):
        for label, replacement in (
            ('skill', '[控制规则]'), ('skills', '[控制规则]'),
            ('SKILL.md', '[控制规则]'), ('goal-prompt', '[控制规则]'),
            ('gpt-6-luna', '[模型标识已隐藏]'), ('GPT-6.1-sol', '[模型标识已隐藏]'),
            ('6-luna', '[模型标识已隐藏]'), ('6-terra', '[模型标识已隐藏]'),
            ('with_skill', '[实验标识已隐藏]'), ('without_skill', '[实验标识已隐藏]'),
            ('arm: current', '[实验标识已隐藏]'),
        ):
            with self.subTest(label=label):
                value, changes = business.redact('来源' + label + '已确认；完成2/10，等待审批。')
                self.assertEqual(value, '来源' + replacement + '已确认；完成2/10，等待审批。')
                self.assertTrue(changes)

    def test_business_words_and_quantities_remain(self):
        text = 'business skillful skillet armchair; 6/10 gates; 42 rows; uncertainty remains.'
        self.assertEqual(business.redact(text), (text, []))


if __name__ == '__main__':
    unittest.main()
