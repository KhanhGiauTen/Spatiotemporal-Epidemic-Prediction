"""Unit tests for Star Cubing algorithm"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import unittest
from star_tree import StarTree
from star_cubing import starcubing


class TestStarCubing(unittest.TestCase):
    def setUp(self):
        self.attributes = ['site', 'age_group', 'sex']
        self.tree = StarTree(self.attributes, min_support=2)
        txns = [
            ['A', '18-34', 'F'],
            ['A', '18-34', 'F'],
            ['A', '35-59', 'M'],
            ['B', '18-34', 'F'],
            ['C', '5-12', 'M'],
        ]
        for t in txns:
            self.tree.insert(t)

    def test_cuboids_min_sup_2(self):
        cuboids = starcubing(self.tree, min_sup=2)
        # Expect at least the (site=A,*,*) cuboid with support 3
        found = any(c[0][0] == 'A' and s >= 2 for c, s in cuboids)
        self.assertTrue(found)

    def test_pruning_low_support(self):
        # value C occurs once -> should be pruned at min_sup=2
        cuboids = starcubing(self.tree, min_sup=2)
        self.assertFalse(any(c[0][0] == 'C' for c, s in cuboids))


if __name__ == '__main__':
    unittest.main()
