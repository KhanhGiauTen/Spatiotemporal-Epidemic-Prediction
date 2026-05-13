# Star Cubing (Iceberg Cube Extraction)

This document describes the `starcubing` algorithm implemented in `src/star_cubing.py`.

## Algorithm Summary

- `starcubing(tree, min_sup)` performs a top-down traversal of the `StarTree`.
- At every visited prefix (node), if the node's support `< min_sup` we **prune** that branch (bottom-up pruning).
- For each node with support >= `min_sup`, we emit the corresponding cuboid (filling remaining dimensions with `*`).
- The result is a list of heavy-hitter cuboids and their support counts.

## Usage

```python
from src import StarTree, starcubing

attributes = ['site', 'age_group', 'sex']
tree = StarTree(attributes, min_support=2)
# insert transactions ...
results = starcubing(tree, min_sup=10)
for cuboid, support in results:
    print(cuboid, support)
```

## Pruning (Shared Dimensions)

The implementation uses node-level counts (prefix support). If a prefix's support is below `min_sup`, it is pruned and its children are not explored. This effectively enforces the Apriori bottom-up pruning condition while traversing top-down.

## Complexity

- Time: O(n) relative to the number of nodes visited (pruning reduces exploration)
- Space: Output size proportional to number of heavy-hitter cuboids

## Files
- `src/star_cubing.py` - Implementation
- `src/star_cubing_tests.py` - Unit tests (2 passing tests)

## Notes
- The function is intentionally simple and focused on correctness; it can be extended to aggregate counts across siblings or to compute candidate merges for bottom-up Apriori layers if needed.
