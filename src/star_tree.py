"""
Star Tree / Prefix Tree Implementation for Trajectory Compression
Optimizes memory usage through __slots__ and star replacement algorithm
"""

from typing import Dict, Iterable, Optional, List, Sequence, Tuple, Any
from collections import defaultdict
import pandas as pd


class StarNode:
    """
    A single node in the Star Tree prefix structure.
    Uses __slots__ for memory optimization.
    
    Attributes:
        attribute_name: Name of the attribute at this node level
        attribute_value: Value of the attribute (can be '*' for wildcard)
        count: Support count for this prefix path
        children: Dictionary mapping child attribute values to child nodes
    """
    __slots__ = ('attribute_name', 'attribute_value', 'count', 'children')
    
    def __init__(
        self,
        attribute_name: Optional[str] = None,
        attribute_value: Optional[str] = None
    ):
        """
        Initialize a StarNode
        
        Args:
            attribute_name: Name of the attribute (e.g., 'site', 'age_group')
            attribute_value: Value of the attribute (e.g., 'Klerksdorp', '18-34')
        """
        self.attribute_name = attribute_name
        self.attribute_value = attribute_value
        self.count = 0
        self.children: Dict[str, 'StarNode'] = {}
    
    def increment_count(self, amount: int = 1) -> None:
        """
        Increment the support count for this node
        
        Args:
            amount: Amount to increment by (default: 1)
        """
        self.count += amount
    
    def add_child(self, attribute_value: str, child_node: 'StarNode') -> None:
        """
        Add a child node to this node
        
        Args:
            attribute_value: The attribute value that keys this child
            child_node: The StarNode child to add
        """
        self.children[attribute_value] = child_node
    
    def get_child(self, attribute_value: str) -> Optional['StarNode']:
        """
        Get a child node by attribute value
        
        Args:
            attribute_value: The attribute value to look up
            
        Returns:
            The child StarNode or None if not found
        """
        return self.children.get(attribute_value)
    
    def has_child(self, attribute_value: str) -> bool:
        """
        Check if a child with given attribute value exists
        
        Args:
            attribute_value: The attribute value to check
            
        Returns:
            True if child exists, False otherwise
        """
        return attribute_value in self.children
    
    def get_memory_size(self) -> int:
        """
        Estimate memory usage of this node and its subtree
        
        Returns:
            Approximate memory size in bytes
        """
        # Base node size
        size = object.__sizeof__(self)
        
        # Add size of strings
        if self.attribute_name:
            size += len(self.attribute_name) * 2  # Unicode characters
        if self.attribute_value:
            size += len(self.attribute_value) * 2
        
        # Add dictionary overhead
        size += self.children.__sizeof__()
        
        # Recursively add children sizes
        for child in self.children.values():
            size += child.get_memory_size()
        
        return size
    
    def __repr__(self) -> str:
        return (
            f"<StarNode({self.attribute_name}={self.attribute_value}, "
            f"count={self.count}, children={len(self.children)})>"
        )
    
    def __str__(self) -> str:
        """String representation of node with indentation"""
        return f"{self.attribute_name}={self.attribute_value}:{self.count}"


class StarTree:
    """
    Star Tree (Prefix Tree) for compressing trajectories/transactions.
    Uses star replacement to reduce memory footprint by replacing infrequent
    attributes with a wildcard '*' operator.
    
    The tree is structured as:
    Root → Attribute1_values → Attribute2_values → ... → Leaf
    """
    
    def __init__(
        self,
        attribute_names: List[str],
        min_support: int = 1,
        star_token: str = '*'
    ):
        """
        Initialize a StarTree
        
        Args:
            attribute_names: List of attribute names in order (e.g., ['site', 'age_group', 'sex'])
            min_support: Minimum support threshold for star replacement
            star_token: Wildcard token used for infrequent values
        """
        if min_support < 1:
            raise ValueError("min_support must be >= 1")

        self.root = StarNode()
        self.attribute_names = attribute_names
        self.num_attributes = len(attribute_names)
        self.min_support = min_support
        self.star_token = star_token
        self.transaction_count = 0
        self._global_support_ready = min_support == 1
        
        # Track attribute value frequencies for star replacement
        self.attribute_frequencies: Dict[str, Dict[str, int]] = {
            attr: defaultdict(int) for attr in attribute_names
        }

    def _validate_transaction(self, transaction: Sequence[str]) -> None:
        """Validate that a transaction matches the configured schema."""
        if len(transaction) != self.num_attributes:
            raise ValueError(
                f"Transaction length {len(transaction)} does not match "
                f"attribute count {self.num_attributes}"
            )

    def reset_tree(self) -> None:
        """Clear the in-memory tree while keeping global frequency counts."""
        self.root = StarNode()
        self.transaction_count = 0

    def fit_global_frequencies(self, transactions: Iterable[Sequence[str]]) -> List[List[str]]:
        """
        Calculate global attribute-value frequencies before tree insertion.

        Star replacement depends on global support, so callers should fit once
        over the full dataset and then insert rows, or call build_from_transactions.

        Args:
            transactions: Full transaction collection

        Returns:
            Materialized transaction list, useful when the input was a generator
        """
        materialized = [list(transaction) for transaction in transactions]

        self.attribute_frequencies = {
            attr: defaultdict(int) for attr in self.attribute_names
        }
        for transaction in materialized:
            self._validate_transaction(transaction)
            for attr_name, attr_value in zip(self.attribute_names, transaction):
                self.attribute_frequencies[attr_name][str(attr_value)] += 1

        self._global_support_ready = True
        return materialized

    def build_from_transactions(self, transactions: Iterable[Sequence[str]]) -> None:
        """
        Build the StarTree with exact global star replacement.

        This is the preferred bulk-loading API for Iceberg Cube extraction.
        It runs a frequency pass first, resets the tree, then inserts each row.
        """
        materialized = self.fit_global_frequencies(transactions)
        self.reset_tree()
        for transaction in materialized:
            self.insert(transaction)
    
    def insert(self, transaction: List[str]) -> None:
        """
        Insert a transaction (row of attributes) into the star tree.
        Automatically applies star replacement based on min_support threshold.
        
        Args:
            transaction: List of attribute values in same order as attribute_names
        """
        self._validate_transaction(transaction)
        if not self._global_support_ready:
            raise RuntimeError(
                "Global frequencies are required for star replacement. "
                "Call fit_global_frequencies() before insert(), or use "
                "build_from_transactions() / load_from_dataframe()."
            )
        
        # Apply star replacement - replace with * if doesn't meet min_support
        replaced_transaction = self._apply_star_replacement([str(v) for v in transaction])
        
        # Insert into tree
        self._insert_path(replaced_transaction)
        self.transaction_count += 1
    
    def _apply_star_replacement(self, transaction: List[str]) -> List[str]:
        """
        Apply star replacement logic: replace attributes that don't meet
        the global minimum support threshold with '*'
        
        Args:
            transaction: Original transaction with all attributes
            
        Returns:
            Transaction with infrequent attributes replaced by '*'
        """
        replaced = []
        for attr_name, attr_value in zip(self.attribute_names, transaction):
            if self.min_support == 1:
                replaced.append(attr_value)
                continue

            freq = self.attribute_frequencies[attr_name][attr_value]
            if freq >= self.min_support:
                replaced.append(attr_value)
            else:
                replaced.append(self.star_token)
        return replaced
    
    def _insert_path(self, transaction: List[str]) -> None:
        """
        Insert a transaction path into the tree structure
        
        Args:
            transaction: Transaction (with star replacement already applied)
        """
        current_node = self.root
        
        for level, (attr_name, attr_value) in enumerate(
            zip(self.attribute_names, transaction)
        ):
            # Get or create child node for this attribute value
            if not current_node.has_child(attr_value):
                child_node = StarNode(attr_name, attr_value)
                current_node.add_child(attr_value, child_node)
            
            current_node = current_node.get_child(attr_value)
            current_node.increment_count()
    
    def get_paths(self, min_count: int = 1) -> List[Tuple[List[Tuple[str, str]], int]]:
        """
        Extract all paths from the tree with their support counts
        
        Args:
            min_count: Minimum count threshold for paths to include
            
        Returns:
            List of (path, count) tuples where path is list of (attr_name, attr_value)
        """
        paths = []
        self._extract_paths(self.root, [], paths, min_count)
        return paths
    
    def _extract_paths(
        self,
        node: StarNode,
        current_path: List[Tuple[str, str]],
        paths: List[Tuple[List[Tuple[str, str]], int]],
        min_count: int
    ) -> None:
        """
        Recursively extract all paths from node
        
        Args:
            node: Current node being processed
            current_path: Path accumulated so far
            paths: List to store results
            min_count: Minimum count threshold
        """
        if node.attribute_name is not None:  # Not root
            current_path = current_path + [(node.attribute_name, node.attribute_value)]
        
        # If this is a complete path and meets threshold, add it
        if len(current_path) == self.num_attributes and node.count >= min_count:
            paths.append((current_path[:], node.count))
        
        # Recursively process children
        for child in node.children.values():
            self._extract_paths(child, current_path, paths, min_count)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the tree
        
        Returns:
            Dictionary with tree statistics
        """
        num_nodes = self._count_nodes(self.root)
        memory_size = self.root.get_memory_size()
        num_paths = len(self.get_paths())
        
        return {
            'transaction_count': self.transaction_count,
            'num_nodes': num_nodes,
            'memory_bytes': memory_size,
            'memory_mb': memory_size / (1024 * 1024),
            'num_paths': num_paths,
            'num_attributes': self.num_attributes,
            'avg_path_length': (
                num_paths / self.transaction_count
                if self.transaction_count > 0
                else 0
            ),
            'compression_ratio': (
                (self.transaction_count * self.num_attributes) / num_nodes
                if num_nodes > 0
                else 0
            )
        }
    
    def _count_nodes(self, node: StarNode) -> int:
        """Count total nodes in subtree"""
        count = 1
        for child in node.children.values():
            count += self._count_nodes(child)
        return count
    
    def print_tree(self, max_depth: int = None) -> str:
        """
        Print tree structure for visualization
        
        Args:
            max_depth: Maximum depth to print (None = all)
            
        Returns:
            String representation of tree
        """
        lines = []
        self._print_tree_recursive(self.root, 0, max_depth, lines)
        return '\n'.join(lines)
    
    def _print_tree_recursive(
        self,
        node: StarNode,
        depth: int,
        max_depth: Optional[int],
        lines: List[str]
    ) -> None:
        """Recursively print tree structure"""
        if max_depth is not None and depth > max_depth:
            return
        
        if node.attribute_name is not None:
            indent = '  ' * depth
            lines.append(f"{indent}├─ {node.attribute_name}={node.attribute_value} [{node.count}]")
        
        for child in node.children.values():
            self._print_tree_recursive(child, depth + 1, max_depth, lines)
    
    def load_from_dataframe(
        self,
        df: pd.DataFrame,
        attribute_columns: List[str],
        calculate_min_support: bool = False
    ) -> None:
        """
        Load transactions from a pandas DataFrame
        
        Args:
            df: DataFrame containing transactions
            attribute_columns: Column names to use as attributes
            calculate_min_support: If True, calculate min_support as 10% of row count
        """
        if calculate_min_support:
            self.min_support = max(1, len(df) // 10)
        
        transactions = [
            [str(row[col]) for col in attribute_columns]
            for _, row in df.iterrows()
        ]
        self.build_from_transactions(transactions)
        
        print(f"✓ Loaded {len(df)} transactions into StarTree")
    
    def get_frequent_patterns(self, min_support: int = None) -> List[Tuple[List[str], int]]:
        """
        Get frequent patterns (paths with minimum support)
        
        Args:
            min_support: Minimum support count (uses tree's min_support if not provided)
            
        Returns:
            List of (path, count) tuples
        """
        if min_support is None:
            min_support = self.min_support
        
        patterns = []
        paths = self.get_paths(min_count=min_support)
        
        for path, count in paths:
            pattern = [f"{name}={value}" for name, value in path]
            patterns.append((pattern, count))
        
        return patterns


if __name__ == '__main__':
    # Example usage
    print("=== StarNode Example ===")
    root = StarNode()
    child = StarNode('site', 'Klerksdorp')
    root.add_child('Klerksdorp', child)
    child.increment_count(5)
    print(f"✓ StarNode created: {child}")
    print(f"✓ Memory usage: {root.get_memory_size()} bytes")
    
    print("\n=== StarTree Example ===")
    attributes = ['site', 'age_group', 'sex']
    tree = StarTree(attributes, min_support=2)
    
    # Insert sample transactions
    transactions = [
        ['Klerksdorp', '18-34', 'Female'],
        ['Klerksdorp', '35-59', 'Male'],
        ['Klerksdorp', '18-34', 'Female'],
        ['Johannesburg', '18-34', 'Male'],
        ['Johannesburg', '5-12', 'Female'],
    ]
    
    tree.build_from_transactions(transactions)
    
    print(tree.print_tree(max_depth=2))
    print("\n✓ Tree Statistics:")
    for key, value in tree.get_statistics().items():
        if isinstance(value, float):
            print(f"  {key}: {value:.4f}")
        else:
            print(f"  {key}: {value}")
