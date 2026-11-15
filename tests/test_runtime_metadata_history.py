"""A historical diagnostic must refuse before starting expensive native work."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run_runtime_virtual_metadata as runner


class HistoricalMetadataTests(unittest.TestCase):
    def test_new_source_refuses_before_budget_or_native_parent(self):
        with patch.object(runner,'source_fingerprint',return_value='new-source',create=True), \
             patch.object(runner,'ensure_budget') as budget, \
             patch.object(runner,'parent_capture',side_effect=AssertionError('native work started')) as parent:
            with self.assertRaisesRegex(ValueError,'historical R2r'):
                runner.capture(Path('unused-python'),Path('unused-sdk'))
            budget.assert_not_called()
            parent.assert_not_called()
