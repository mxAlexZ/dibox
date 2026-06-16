"""Fixture module using from __future__ import annotations.

Required to be a separate module because the future import affects the entire module
at compile time — annotations become lazily-evaluated strings instead of live types.
"""
from __future__ import annotations


class FutureLeaf:
    pass


class FutureBranch:
    def __init__(self, leaf: FutureLeaf):
        self.leaf = leaf
