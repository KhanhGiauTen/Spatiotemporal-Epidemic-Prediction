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
        self.tree.build_from_transactions(txns)

    def test_cuboids_min_sup_2(self):
        cuboids = starcubing(self.tree, min_sup=2)
        # Expect at least the (site=A,*,*) cuboid with support 3
        found = any(c[0][0] == 'A' and s >= 2 for c, s in cuboids)
        self.assertTrue(found)

    def test_pruning_low_support(self):
        # value C occurs once -> should be pruned at min_sup=2
        cuboids = starcubing(self.tree, min_sup=2)
        self.assertFalse(any(c[0][0] == 'C' for c, s in cuboids))

    def test_finds_non_prefix_heavy_hitter(self):
        tree = StarTree(self.attributes, min_support=1)
        tree.build_from_transactions([
            ['A', '18-34', 'F'],
            ['B', '18-34', 'M'],
        ])

        cuboids = starcubing(tree, min_sup=2)
        self.assertIn((['*', '18-34', '*'], 2), cuboids)

    def test_algorithm_package_export(self):
        from algorithm import starcubing as package_starcubing

        cuboids = package_starcubing(self.tree, min_sup=2)
        self.assertEqual(cuboids, starcubing(self.tree, min_sup=2))


if __name__ == '__main__':
    unittest.main()
