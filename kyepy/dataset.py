from __future__ import annotations
from pydantic import BaseModel, constr, model_validator

TYPE = constr(pattern=r'[A-Z][a-z][a-zA-Z]*')
EDGE = constr(pattern=r'[a-z][a-z_]*')
TYPE_REF = constr(pattern=r'[A-Z][a-z][a-zA-Z]*(\.[A-Za-z]+)*')

class Edge(BaseModel):
    type: TYPE_REF
    nullable: bool = False
    multiple: bool = False
    # TODO: Maybe this reference to the environment doesn't get added until
    # the type/edge is accessed through that environment?
    # Might allow for the type to switch environments, but I'm not sure if
    # that is something I'll ever need.
    # Or just create another class that wraps this one and adds the environment
    _dataset: dict = None

    @property
    def _type(self):
        return self._dataset.get(self.type)

    def __repr__(self):
        return "Edge<{}{}>".format(
            self._type.name or '',
            ([['' ,'+'],
              ['?','*']])[int(self.nullable)][int(self.multiple)],
        )

class Type(BaseModel):
    name: TYPE = None
    extends: TYPE_REF = None
    indexes: list[list[EDGE]] = []
    edges: dict[EDGE, Edge] = {}
    _dataset: dict = None

    @property
    def _extends(self):
        return self._dataset.get(self.extends)

    @property
    def inheritance_chain(self):
        if self._extends is None:
            return [self]
        return self._extends.inheritance_chain + [self]
    
    def issubclass(self, other: TYPE_REF):
        if self.name == other:
            return True
        if self._extends is None:
            return False
        return self._extends.issubclass(other)

    @model_validator(mode='before')
    @classmethod
    def determine_extends(self, data):
        if type(data) is dict:
            if data.get('extends') is None:
                if len(data.get('indexes',[])) > 0:
                    data['extends'] = "Model"
        return data

    def __getitem__(self, name: EDGE):
        return self.edges[name]

    def __contains__(self, name: EDGE):
        return name in self.edges

    def __repr__(self):
        all_indexes = [idx for idxs in self.indexes for idx in idxs]
        non_index_edges = [edge for edge in self.edges.keys() if edge not in all_indexes]
        return "Type<{}{}{}{}>".format(
            self.name or '',
            ':' + self._extends.name if self._extends and self._extends.name else '',
            ''.join('(' + ','.join(idx) + ')' for idx in self.indexes),
            '{' + ','.join(non_index_edges) + '}' if len(non_index_edges) else '',
        )

GLOBALS = {
    'Number': Type(name='Number'),
    'Boolean': Type(name='Boolean'),
    'String': Type(name='String', edges={'length': Edge(type='Number')}),
    'Struct': Type(name='Struct'),
    'Model': Type(name='Model', extends='Struct'),
}

class Dataset(BaseModel):
    models: dict[TYPE_REF, Type] = {}

    @model_validator(mode='before')
    @classmethod
    def add_globals(self, data):
        if type(data) is dict:
            for name, model in GLOBALS.items():
                if name not in data['models']:
                    data['models'][name] = model
        return data

    @model_validator(mode='after')
    def resolve_references(self):
        for model in self.models.values():
            model._dataset = self
            for edge in model.edges.values():
                edge._dataset = self
        return self
    
    def get(self, ref: TYPE_REF, default=None):
        return self.models.get(ref, default)
    
    def __getitem__(self, ref: TYPE_REF):
        return self.models[ref]

    def __contains__(self, ref: TYPE_REF):
        return ref in self.models

    def __repr__(self):
        return "Dataset<{}>".format(
            ','.join(ref + (':' + model.name if model.name and model.name != ref else '') for ref, model in self.models.items() if ref not in GLOBALS),
        )

