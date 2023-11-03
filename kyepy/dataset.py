from __future__ import annotations
from pydantic import BaseModel, constr, model_validator

TYPE = constr(pattern=r'[A-Z][a-z][a-zA-Z]*')
EDGE = constr(pattern=r'[a-z][a-z_]*')
TYPE_REF = constr(pattern=r'[A-Z][a-z][a-zA-Z]*(\.[A-Za-z]+)*')

class Edge(BaseModel):
    type: TYPE_REF
    nullable: bool = False
    multiple: bool = False

    @property
    def _type(self):
        return self._dataset.get(self.type)

    def __repr__(self):
        return "Edge<{}{}>".format(
            self.type or '',
            ([['' ,'+'],
              ['?','*']])[int(self.nullable)][int(self.multiple)],
        )

class Type(BaseModel):
    name: TYPE = None
    extends: TYPE_REF = None
    indexes: list[list[EDGE]] = []
    edges: dict[EDGE, Edge] = {}

    def __getitem__(self, name: EDGE):
        return self.edges[name]

    def __contains__(self, name: EDGE):
        return name in self.edges

    def __repr__(self):
        all_indexes = [idx for idxs in self.indexes for idx in idxs]
        non_index_edges = [edge for edge in self.edges.keys() if edge not in all_indexes]
        return "Type<{}{}{}{}>".format(
            self.name or '',
            ':' + self.extends if self.extends else '',
            ''.join('(' + ','.join(idx) + ')' for idx in self.indexes),
            '{' + ','.join(non_index_edges) + '}' if len(non_index_edges) else '',
        )

class Dataset(BaseModel):
    models: dict[TYPE_REF, Type] = {}
    
    def get(self, ref: TYPE_REF, default=None):
        return self.models.get(ref, default)
    
    def __getitem__(self, ref: TYPE_REF):
        return self.models[ref]

    def __contains__(self, ref: TYPE_REF):
        return ref in self.models

    def __repr__(self):
        return "Dataset<{}>".format(
            ','.join(ref + (':' + model.name if model.name and model.name != ref else '') for ref, model in self.models.items()),
        )

