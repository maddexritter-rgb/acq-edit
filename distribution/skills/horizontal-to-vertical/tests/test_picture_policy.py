import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from picture_policy import mirror_update

class MirrorIntentTests(unittest.TestCase):
    def test_second_pass_does_not_flip_back(self):
        first=mirror_update(item_flip=False,ancestor_flips=[],intended_effective_flip=True)
        self.assertTrue(first['change'])
        second=mirror_update(item_flip=first['item_flip_after'],ancestor_flips=[],intended_effective_flip=True)
        self.assertFalse(second['change'])

    def test_parent_mirror_already_supplies_the_intended_picture(self):
        plan=mirror_update(item_flip=False,ancestor_flips=[True],intended_effective_flip=True)
        self.assertFalse(plan['change'])

    def test_two_existing_mirrors_are_corrected_with_one_item_change(self):
        plan=mirror_update(item_flip=True,ancestor_flips=[True],intended_effective_flip=True)
        self.assertFalse(plan['current_effective_flip'])
        self.assertTrue(plan['change'])
        self.assertFalse(plan['item_flip_after'])

    def test_unknown_parent_is_inspected_not_guessed(self):
        plan=mirror_update(item_flip=False,ancestor_flips=[None],intended_effective_flip=True)
        self.assertEqual(plan['status'],'NEEDS_INSPECTION')
        self.assertFalse(plan['change'])

if __name__=='__main__':unittest.main()
