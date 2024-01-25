from __future__ import annotations
from pydantic import BaseModel, model_validator, constr
from typing import Optional, Union, Literal

TYPE = constr(pattern=r'[A-Z][a-z][a-zA-Z]*')
EDGE = constr(pattern=r'[a-z][a-z_]*')
POSTFIXED_EDGE = constr(pattern=r'[a-z][a-z_]*[*+?]?')
TYPE_REF = constr(pattern=r'([A-Z]+[a-z][A-Za-z_]*)(\.[A-Za-z_]+)*')

class Models(BaseModel):
    models: dict[TYPE_REF, Type]

class Type(BaseModel):
    index: Optional[Union[EDGE, list[EDGE]]] = None
    indexes: Optional[Union[list[EDGE], list[list[EDGE]]]] = None
    edges: dict[POSTFIXED_EDGE,TYPE_REF]
    extends: Optional[TYPE_REF] = None
    assertions: list[Assertion] = []

    @model_validator(mode='after')
    def check_not_both_index_and_indexes(self):
        if self.index is not None and self.indexes is not None:
            raise ValueError('cant have both `index` and `indexes` defined')
        return self

LiteralType = Union[float,str,bool]

class Edge(BaseModel):
    type: TYPE_REF

class Assertion(BaseModel):
    type: Optional[Literal['string','number','boolean']] = None
    eq: Optional[LiteralType] = None
    ne: Optional[LiteralType] = None
    gt: Optional[float] = None
    gte: Optional[float] = None
    lt: Optional[float] = None
    lte: Optional[float] = None

    @model_validator(mode='after')
    def check_only_one_assertion(self):
        if len(self.model_fields_set) != 1:
            raise ValueError('Expected one and only one assertion operator')
        return self
    
    @property
    def op(self):
        return list(self.model_fields_set)[0]
    
    @property
    def arg(self):
        return getattr(self, self.op)