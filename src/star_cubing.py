"""
Star Cubing: Top-down (with Bottom-up pruning) Iceberg Cube extraction

Exports:
- starcubing(tree: StarTree, min_sup: int) -> List[Tuple[List[str], int]]

Algorithm:
- Traverse the StarTree top-down.
- At each node, if node.count < min_sup then prune (do not explore children).
- Otherwise, emit the cuboid corresponding to the current path (fill remaining dims with '*').
- Recurse into children to generate more specific cuboids.

This implements the combined Top-down (traverse) + Bottom-up (prune low-support branches)
strategy required for Iceberg Cube extraction.
"""
from typing import List, Tuple, Any

try:
    # When used as package
    from .star_tree import StarTree, StarNode
except Exception:
    # When tests/scripts run from src directory directly
    from star_tree import StarTree, StarNode


def _make_cuboid_from_path(path: List[Tuple[str, str]], total_dims: int) -> List[str]:
    """Convert a partial path (list of (attr_name, value)) into a full cuboid
    by filling remaining dimensions with '*' in order.
    The function returns only the attribute values in order (not names).
    """
    values = [v for (_, v) in path]
    # fill remaining dims with '*'
    if len(values) < total_dims:
        values.extend(['*'] * (total_dims - len(values)))
    return values


def starcubing(tree: StarTree, min_sup: int) -> List[Tuple[List[str], int]]:
    """
    Extract iceberg cuboids (heavy-hitters) from a StarTree using a
    top-down traversal with pruning (shared-dimension check).

    Args:
        tree: StarTree instance
        min_sup: Minimum support threshold for cuboids

    Returns:
        List of tuples (cuboid_values_list, support_count)
        where cuboid_values_list is a list of attribute values (order matches tree.attribute_names)
    """
    results: List[Tuple[List[str], int]] = []

    def recurse(node: StarNode, depth: int, path: List[Tuple[str, str]]):
        # If current node has support below min_sup, prune immediately
        if node is not None and depth > 0 and node.count < min_sup:
            return

        # If depth>0, node corresponds to a concrete attribute at level depth
        if depth > 0 and node is not None:
            # emit cuboid corresponding to the path so far
            cuboid = _make_cuboid_from_path(path, tree.num_attributes)
            support = node.count
            if support >= min_sup:
                results.append((cuboid, support))

        # If depth == tree.num_attributes, reached leaf-level (no further dims)
        if depth >= tree.num_attributes:
            return

        # Traverse children (Top-down)
        children_items = list(node.children.items()) if node is not None else []
        for value, child in children_items:
            # Shared-dimension pruning: if aggregated child's count < min_sup, skip
            # (child.count already reflects support of that prefix)
            if child.count < min_sup:
                continue
            recurse(child, depth + 1, path + [(child.attribute_name, child.attribute_value)])

    # Start recursion from root
    recurse(tree.root, 0, [])
    return results


if __name__ == '__main__':
    # small demo when run directly
    from .star_tree import StarTree

    attributes = ['site', 'age_group', 'sex']
    tree = StarTree(attributes, min_support=2)

    transactions = [
        ['Klerksdorp', '18-34', 'Female'],
        ['Klerksdorp', '35-59', 'Male'],
        ['Klerksdorp', '18-34', 'Female'],
        ['Johannesburg', '18-34', 'Male'],
        ['Johannesburg', '5-12', 'Female'],
    ]

    for txn in transactions:
        tree.insert(txn)

    cuboids = starcubing(tree, min_sup=2)
    print("Cuboids (value-vector) with support >= 2:")
    for c, s in cuboids:
        print(c, s)
