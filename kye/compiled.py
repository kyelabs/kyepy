from __future__ import annotations
import typing as t
from dataclasses import dataclass
from functools import cached_property, cache

from kye.vm.op import OP, parse_command

@dataclass(frozen=True)
class Cmd:
    op: OP
    args: t.List
    
    @staticmethod
    def from_dict(data: dict) -> Cmd:
        op, args = parse_command(data)
        return Cmd(op, args)

    def to_dict(self) -> dict:
        args = self.args
        if len(args) == 1:
            args = args[0]
        return {self.op.name.lower(): args}

    @cached_property
    def num_stack_args(self) -> int:
        return self.op.arity - len(self.args)

Expr = t.List[Cmd]

@dataclass(frozen=True)
class Assertion:
    model: str
    msg: str
    expr: Expr
    loc: t.Optional[str]
    
    @staticmethod
    def from_dict(model: str, data: dict) -> Assertion:
        return Assertion(
            model=model,
            msg=data['msg'],
            expr=[
                Cmd.from_dict(cmd)
                for cmd in data['expr']
            ],
            loc=data.get('loc')
        )
    
    def to_dict(self) -> dict:
        compiled = {
            'msg': self.msg,
            'expr': [
                cmd.to_dict()
                for cmd in self.expr
            ],
        }
        if self.loc:
            compiled['loc'] = str(self.loc)
        return compiled

    @cached_property
    def edges(self) -> t.List[str]:
        edges = set()
        for cmd in self.expr:
            if cmd.op == OP.COL:
                assert len(cmd.args) == 1
                edges.add(cmd.args[0])
        return list(edges)

@dataclass(frozen=True)
class Edge():
    model: str
    name: str
    null: bool
    many: bool
    type: str
    title: t.Optional[str]
    expr: t.Optional[Expr]
    loc: t.Optional[str]
    
    @staticmethod
    def from_dict(model: str, name: str, data: dict) -> Edge:
        return Edge(
            model=model,
            name=name,
            title=data.get('title'),
            null=data.get('null', False),
            many=data.get('many', False),
            type=data['type'],
            expr=[
                Cmd.from_dict(cmd)
                for cmd in data['expr']
            ] if 'expr' in data else None,
            loc=data.get('loc')
        )
    
    def to_dict(self) -> dict:
        data: dict = {
            'type': self.type,
        }
        if self.title:
            data['title'] = self.title
        if self.expr:
            data['expr'] = [
                cmd.to_dict()
                for cmd in self.expr
            ]
        if self.many:
            data['many'] = True
        if self.null:
            data['null'] = True
        if self.loc:
            data['loc'] = str(self.loc)
        return data

    @cached_property
    def cardinality(self) -> str:
        if self.many:
            if self.null:
                return 'many'
            else:
                return 'more'
        else:
            if self.null:
                return 'maybe'
            else:
                return 'one'

@dataclass(frozen=True)
class Type():
    name: str
    parent: t.Optional[str]
    conditions: t.Optional[Expr]
    edges: t.Dict[str, Edge]
    assertions: t.List[Assertion]
    loc: t.Optional[str]
    
    @staticmethod
    def from_dict(name: str, data: dict) -> Type:
        return Type(
            name=name,
            parent=data.get('parent'),
            conditions=[
                Cmd.from_dict(cmd)
                for cmd in data['conditions']
            ] if 'conditions' in data else None,
            edges={
                edge_name: Edge.from_dict(name, edge_name, edge)
                for edge_name, edge in data.get('edges',{}).items()
            },
            assertions=[
                Assertion.from_dict(name, assertion)
                for assertion in data.get('assertions', [])
            ],
            loc=data.get('loc')
        )
    
    def to_dict(self) -> dict:
        compiled = {}
        if self.parent:
            compiled['parent'] = self.parent
        if self.conditions:
            compiled['conditions'] = [
                condition.to_dict()
                for condition in self.conditions
            ]
        if len(self.edges) > 0:
            compiled['edges'] = {
                edge_name: edge.to_dict()
                for edge_name, edge in self.edges.items()
            }
        if len(self.assertions) > 0:
            compiled['assertions'] = [
                assertion.to_dict()
                for assertion in self.assertions
            ]
        if self.loc:
            compiled['loc'] = str(self.loc)
        return compiled

    def __getitem__(self, key: str) -> Edge:
        return self.edges[key]
    
    def __contains__(self, key: str) -> bool:
        return key in self.edges
    

@dataclass(frozen=True)
class Model():
    name: str
    indexes: t.List[t.List[str]]
    edges: t.Dict[str, Edge]
    assertions: t.List[Assertion]
    loc: t.Optional[str]
    
    @staticmethod
    def from_dict(model_name: str, data: dict) -> Model:
        return Model(
            name=model_name,
            indexes=data['indexes'],
            edges={
                edge_name: Edge.from_dict(model_name, edge_name, edge)
                for edge_name, edge in data['edges'].items()
            },
            assertions=[
                Assertion.from_dict(model_name, assertion)
                for assertion in data.get('assertions',[])
            ],
            loc=data.get('loc')
        )
    
    def to_dict(self) -> dict:
        compiled = {
            'indexes': self.indexes,
            'edges': {
                edge.name: edge.to_dict()
                for edge in self.edges.values()
            },
        }
        if len(self.assertions) > 0:
            compiled['assertions'] = [
                assertion.to_dict()
                for assertion in self.assertions
            ]
        if self.loc:
            compiled['loc'] = str(self.loc)
        return compiled
    
    @cached_property
    def index(self) -> t.List[str]:
        index_edges = set()
        for index in self.indexes:
            for edge in index:
                index_edges.add(edge)
        return list(index_edges)

    def __getitem__(self, key: str) -> Edge:
        return self.edges[key]
    
    def __contains__(self, key: str) -> bool:
        return key in self.edges

@dataclass(frozen=True)
class Compiled():
    types: t.Dict[str, Type]
    models: t.Dict[str, Model]
    
    @staticmethod
    def from_dict(data: dict) -> Compiled:
        return Compiled(
            types={
                name: Type.from_dict(name, type)
                for name, type in data.get('types', {}).items()
            },
            models={
                name: Model.from_dict(name, model)
                for name, model in data['models'].items()
            }
        )
    
    def to_dict(self) -> dict:
        compiled = {
            'models': {
                model.name: model.to_dict()
                for model in self.models.values()
            }
        }
        if len(self.types) > 0:
            compiled['types'] = {
                type.name: type.to_dict()
                for type in self.types.values()
            }
        return compiled

    def __getitem__(self, key: str) -> t.Union[Type, Model]:
        if key in self.types:
            return self.types[key]
        return self.models[key]

    def __contains__(self, key: str) -> bool:
        if key in self.types:
            return True
        return key in self.models

    def __or__(self, other: Compiled) -> Compiled:
        return Compiled(
            types={**self.types, **other.types},
            models={**self.models, **other.models},
        )

@cache
def native_types():
    from pathlib import Path
    import json
    path = Path(__file__).parent / 'native_types.kye.json'
    with path.open() as f:
        data = json.load(f)
        return Compiled.from_dict(data)