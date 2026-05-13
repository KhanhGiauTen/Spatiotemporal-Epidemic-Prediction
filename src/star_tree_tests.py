"""
Tests and demonstrations for Star Tree implementation
Includes unit tests and real-world usage examples with epidemic data
"""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

import unittest
import pandas as pd
import numpy as np
from star_tree import StarNode, StarTree


class TestStarNode(unittest.TestCase):
    """Unit tests for StarNode class"""
    
    def test_star_node_creation(self):
        """Test StarNode initialization"""
        node = StarNode('site', 'Klerksdorp')
        self.assertEqual(node.attribute_name, 'site')
        self.assertEqual(node.attribute_value, 'Klerksdorp')
        self.assertEqual(node.count, 0)
        self.assertEqual(len(node.children), 0)
    
    def test_star_node_increment_count(self):
        """Test count incrementing"""
        node = StarNode('site', 'Klerksdorp')
        node.increment_count()
        self.assertEqual(node.count, 1)
        node.increment_count(5)
        self.assertEqual(node.count, 6)
    
    def test_star_node_child_management(self):
        """Test adding and retrieving child nodes"""
        parent = StarNode()
        child = StarNode('age_group', '18-34')
        
        parent.add_child('18-34', child)
        self.assertTrue(parent.has_child('18-34'))
        self.assertEqual(parent.get_child('18-34'), child)
        self.assertFalse(parent.has_child('35-59'))
    
    def test_star_node_memory_calculation(self):
        """Test memory size estimation"""
        node = StarNode('site', 'Klerksdorp')
        memory = node.get_memory_size()
        self.assertGreater(memory, 0)


class TestStarTree(unittest.TestCase):
    """Unit tests for StarTree class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.attributes = ['site', 'age_group', 'sex']
        self.tree = StarTree(self.attributes, min_support=1)
    
    def test_tree_initialization(self):
        """Test StarTree initialization"""
        self.assertEqual(self.tree.num_attributes, 3)
        self.assertEqual(self.tree.attribute_names, self.attributes)
        self.assertEqual(self.tree.transaction_count, 0)
    
    def test_single_transaction_insert(self):
        """Test inserting a single transaction"""
        transaction = ['Klerksdorp', '18-34', 'Female']
        self.tree.insert(transaction)
        self.assertEqual(self.tree.transaction_count, 1)
    
    def test_multiple_transactions_insert(self):
        """Test inserting multiple transactions"""
        transactions = [
            ['Klerksdorp', '18-34', 'Female'],
            ['Klerksdorp', '35-59', 'Male'],
            ['Johannesburg', '18-34', 'Female'],
        ]
        for txn in transactions:
            self.tree.insert(txn)
        
        self.assertEqual(self.tree.transaction_count, 3)
    
    def test_star_replacement(self):
        """Test star replacement logic"""
        tree = StarTree(self.attributes, min_support=2)
        
        # Insert same transaction 3 times (should NOT be replaced)
        for _ in range(3):
            tree.insert(['Klerksdorp', '18-34', 'Female'])
        
        # Insert different transaction once (should be replaced with *)
        tree.insert(['Johannesburg', '5-12', 'Male'])
        
        # Check that frequencies are correct
        self.assertEqual(
            tree.attribute_frequencies['site']['Klerksdorp'], 3
        )
        self.assertEqual(
            tree.attribute_frequencies['site']['Johannesburg'], 1
        )
    
    def test_transaction_validation(self):
        """Test transaction length validation"""
        with self.assertRaises(ValueError):
            self.tree.insert(['Klerksdorp', '18-34'])  # Missing one attribute
    
    def test_get_statistics(self):
        """Test statistics calculation"""
        transactions = [
            ['Klerksdorp', '18-34', 'Female'],
            ['Klerksdorp', '18-34', 'Female'],
            ['Johannesburg', '35-59', 'Male'],
        ]
        for txn in transactions:
            self.tree.insert(txn)
        
        stats = self.tree.get_statistics()
        self.assertEqual(stats['transaction_count'], 3)
        self.assertGreater(stats['num_nodes'], 0)
        self.assertGreater(stats['memory_bytes'], 0)
    
    def test_get_frequent_patterns(self):
        """Test frequent pattern extraction"""
        transactions = [
            ['Klerksdorp', '18-34', 'Female'],
            ['Klerksdorp', '18-34', 'Female'],
            ['Klerksdorp', '18-34', 'Male'],
            ['Johannesburg', '35-59', 'Female'],
        ]
        for txn in transactions:
            self.tree.insert(txn)
        
        patterns = self.tree.get_frequent_patterns(min_support=2)
        self.assertGreater(len(patterns), 0)


class StarTreeDemonstration:
    """Demonstration of StarTree with real epidemic data"""
    
    @staticmethod
    def load_epidemic_data(csv_path=None):
        """Load epidemic data from CSV"""
        if csv_path is None:
            default_paths = [
                Path('data/processed/sashts_final_dataset.csv'),
                Path('../data/processed/sashts_final_dataset.csv'),
                Path('../../data/processed/sashts_final_dataset.csv'),
            ]
            
            for path in default_paths:
                if path.exists():
                    csv_path = str(path)
                    break
            else:
                raise FileNotFoundError("Could not find epidemic dataset")
        
        df = pd.read_csv(csv_path)
        print(f"✓ Loaded {len(df)} records from {csv_path}")
        return df
    
    @staticmethod
    def demo_basic_usage():
        """Demonstrate basic StarTree usage"""
        print("\n" + "="*70)
        print("DEMO 1: Basic StarTree Usage")
        print("="*70)
        
        attributes = ['site', 'age_group', 'sex']
        tree = StarTree(attributes, min_support=2)
        
        transactions = [
            ['Klerksdorp', '18-34', 'Female'],
            ['Klerksdorp', '35-59', 'Male'],
            ['Klerksdorp', '18-34', 'Female'],
            ['Johannesburg', '18-34', 'Male'],
            ['Johannesburg', '5-12', 'Female'],
            ['Cape Town', '18-34', 'Female'],
        ]
        
        print(f"\nInserting {len(transactions)} transactions...")
        for i, txn in enumerate(transactions, 1):
            tree.insert(txn)
        
        print("\n📊 Tree Structure:")
        print(tree.print_tree(max_depth=2))
        
        print("\n📈 Tree Statistics:")
        stats = tree.get_statistics()
        for key, value in stats.items():
            if isinstance(value, float):
                print(f"  • {key}: {value:.4f}")
            else:
                print(f"  • {key}: {value}")
        
        print("\n🔍 Frequent Patterns (min_support=2):")
        patterns = tree.get_frequent_patterns(min_support=2)
        for pattern, count in patterns:
            print(f"  • {' | '.join(pattern)} [{count}]")
    
    @staticmethod
    def demo_star_replacement_effect():
        """Demonstrate the effect of star replacement on tree size"""
        print("\n" + "="*70)
        print("DEMO 2: Star Replacement Effect on Memory Usage")
        print("="*70)
        
        attributes = ['location', 'attribute2', 'attribute3']
        transactions = []
        
        # Generate synthetic data with uneven distribution
        locations = ['Location_A'] * 100 + ['Location_B'] * 10 + ['Location_C'] * 5
        attr2 = ['Value_X'] * 80 + ['Value_Y'] * 35
        attr3 = ['Value_1'] * 70 + ['Value_2'] * 45
        
        for loc, a2, a3 in zip(locations, attr2, attr3):
            transactions.append([loc, a2, a3])
        
        print(f"\nGenerating {len(transactions)} synthetic transactions...")
        print("  • Location: 100x A, 10x B, 5x C")
        print("  • Attr2: 80x X, 35x Y")
        print("  • Attr3: 70x 1, 45x 2")
        
        # Test with different min_support values
        min_supports = [1, 5, 10]
        
        for min_sup in min_supports:
            tree = StarTree(attributes, min_support=min_sup)
            
            for txn in transactions:
                tree.insert(txn)
            
            stats = tree.get_statistics()
            print(f"\n  Min Support = {min_sup}:")
            print(f"    • Nodes: {stats['num_nodes']}")
            print(f"    • Memory: {stats['memory_bytes']:,} bytes")
            print(f"    • Compression: {stats['compression_ratio']:.2f}x")


def run_all_tests():
    """Run all unit tests"""
    print("\n" + "="*70)
    print("RUNNING UNIT TESTS")
    print("="*70)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestStarNode))
    suite.addTests(loader.loadTestsFromTestCase(TestStarTree))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    # Run unit tests
    tests_passed = run_all_tests()
    
    if not tests_passed:
        print("\n✗ Some tests failed!")
        sys.exit(1)
    
    print("\n✓ All tests passed!")
    
    # Run demonstrations
    try:
        demo = StarTreeDemonstration()
        demo.demo_basic_usage()
        demo.demo_star_replacement_effect()
        print("\n" + "="*70)
        print("✓ All demonstrations completed successfully!")
        print("="*70)
    except Exception as e:
        print(f"\n✗ Error during demonstration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
