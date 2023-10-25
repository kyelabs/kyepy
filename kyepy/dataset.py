from __future__ import annotations
from pydantic import BaseModel, constr, model_validator

TYPE = constr(pattern=r'[A-Z][a-z][a-zA-Z]*')
EDGE = constr(pattern=r'[a-z][a-z_]*')
TYPE_REF = constr(pattern=r'[A-Z][a-z][a-zA-Z]*(\.[A-Za-z]+)*')

class Edge(BaseModel):
    type: TYPE_REF
    _type: Type = None
    nullable: bool = False
    multiple: bool = False

    def __repr__(self):
        return "Edge<{}{}>".format(
            self._type.name or '',
            ([['' ,'+'],
              ['?','*']])[int(self.nullable)][int(self.multiple)],
        )

class Type(BaseModel):
    name: TYPE = None
    extends: TYPE_REF = None
    _extends: Type = None
    indexes: list[list[EDGE]] = []
    edges: dict[EDGE, Edge] = {}

    def __getitem__(self, name: EDGE):
        return self.edges[name]

    def __contains__(self, name: EDGE):
        return name in self.edges

    def __repr__(self):
        all_indexes = [idx for idxs in self.indexes for idx in idxs]
        non_index_edges = [edge for edge in self.edges.keys() if edge not in all_indexes]
        return "Type<{}{}{}>".format(
            self.name or '',
            ''.join('(' + ','.join(idx) + ')' for idx in self.indexes),
            '{' + ','.join(non_index_edges) + '}' if len(non_index_edges) else '',
        )

GLOBALS = {
    'Number': Type(name='Number'),
    'String': Type(name='String', edges={'length': Edge(type='Number')}),
}

class Dataset(BaseModel):

    models: dict[TYPE_REF, Type] = {}

    @model_validator(mode='after')
    def resolve_references(self):
        for model in self.models.values():
            if model.extends is not None:
                model._extends = self[model.extends]
            for edge in model.edges.values():
                edge._type = self[edge.type]
    
    def __getitem__(self, ref: TYPE_REF):
        if ref in self.models:
            return self.models[ref]
        if ref in GLOBALS:
            return GLOBALS[ref]
        raise KeyError(ref)

    def __contains__(self, ref: TYPE_REF):
        return ref in self.models or ref in GLOBALS

    def __repr__(self):
        return "Dataset<{}>".format(
            ','.join(ref + (':' + model.name if model.name and model.name != ref else '') for ref, model in self.models.items()),
        )

