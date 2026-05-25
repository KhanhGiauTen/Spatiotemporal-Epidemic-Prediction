# Star Cubing (Iceberg Cube Extraction)

This document describes the `starcubing` algorithm implemented in
`src/algorithm/starcubing.py` and re-exported by `src/star_cubing.py`.

## Algorithm Summary

- `starcubing(tree, min_sup)` reads compressed rows from the `StarTree`.
- The recursive pass walks dimensions top-down and explores both aggregate (`*`) and concrete-value branches.
- Concrete branches whose shared support `< min_sup` are pruned immediately by the Apriori rule.
- The result is a deterministic list of heavy-hitter cuboids and their support counts.

## Usage

```python
from src import StarTree, starcubing

attributes = ['site', 'age_group', 'sex']
tree = StarTree(attributes, min_support=2)
tree.build_from_transactions(transactions)
results = starcubing(tree, min_sup=10)
for cuboid, support in results:
    print(cuboid, support)
```

## Pruning (Shared Dimensions)

The implementation groups the currently shared row set by each dimension. If a
concrete value branch has support below `min_sup`, every more-specific cuboid
under that branch is pruned. The aggregate `*` branch remains available, so
heavy hitters such as `(*, 18-34, *)` are still discovered even when no single
first-dimension prefix is frequent.

## Complexity

- Time: O(n) relative to the number of nodes visited (pruning reduces exploration)
- Space: Output size proportional to number of heavy-hitter cuboids

## Files
- `src/algorithm/starcubing.py` - Implementation and SQL export
- `src/star_cubing.py` - Backwards-compatible import wrapper
- `src/star_cubing_tests.py` - Unit tests for pruning, non-prefix cuboids, and imports

## Notes
- The function emits value vectors in the same dimension order as `tree.attribute_names`.
