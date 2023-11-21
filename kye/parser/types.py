from __future__ import annotations
from typing import Optional

class Type:
    ref: Optional[str] = None
    name: Optional[str] = None
    extends: Optional[str] = None
    indexes: list[list[str]] = []
    edges: dict[str, Type] = {}

    def __init__(self,
                 ref: str = None,
                 name: str = None,
                 extends: str = None,
                 indexes: list[list[str]] = [],
                 edges: dict[str, Type] = {}):
        self.ref = ref
        self.name = name
        self.extends = extends
        self.indexes = indexes
        self.edges = edges

    def __getitem__(self, name: str):
        return self.edges[name]

    def __contains__(self, name: str):
        return name in self.edges

    def __repr__(self):
        all_indexes = [idx for idxs in self.indexes for idx in idxs]
        non_index_edges = [edge for edge in self.edges.keys() if edge not in all_indexes]
        return "Type<{}{}{}{}>".format(
            self.ref or self.name or '',
            ':' + self.extends if self.extends else '',
            ''.join('(' + ','.join(idx) + ')' for idx in self.indexes),
            '{' + ','.join(non_index_edges) + '}' if len(non_index_edges) else '',
        )