"""
Star Tree / Prefix Tree Implementation for Trajectory Compression
Optimizes memory usage through __slots__ and star replacement algorithm
"""

from typing import Dict, Optional, List, Tuple, Any
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


if __name__ == '__main__':
    # Example usage
    root = StarNode()
    child = StarNode('site', 'Klerksdorp')
    root.add_child('Klerksdorp', child)
    child.increment_count(5)
    print(f"✓ StarNode created: {child}")
    print(f"✓ Memory usage: {root.get_memory_size()} bytes")
