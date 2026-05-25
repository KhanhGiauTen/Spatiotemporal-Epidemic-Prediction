"""Compatibility wrapper for the Star-Cubing implementation."""

try:
    from .algorithm.starcubing import starcubing
except Exception:  # pragma: no cover - direct script execution from src/
    from algorithm.starcubing import starcubing


__all__ = ["starcubing"]


if __name__ == '__main__':
    from star_tree import StarTree

    attributes = ['site', 'age_group', 'sex']
    transactions = [
        ['Klerksdorp', '18-34', 'Female'],
        ['Klerksdorp', '35-59', 'Male'],
        ['Klerksdorp', '18-34', 'Female'],
        ['Johannesburg', '18-34', 'Male'],
        ['Johannesburg', '5-12', 'Female'],
    ]

    tree = StarTree(attributes, min_support=2)
    tree.build_from_transactions(transactions)

    cuboids = starcubing(tree, min_sup=2)
    print("Cuboids (value-vector) with support >= 2:")
    for cuboid, support in cuboids:
        print(cuboid, support)
