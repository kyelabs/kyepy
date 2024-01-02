from __future__ import annotations
from typing import Optional, Literal, Union
import kye.parser.kye_ast as AST
import kye.types as Types

class Meta:
    kind: Literal['edge', 'type']
    user_defined: bool
    type_ref: str

    def __init__(self, kind: Literal['edge', 'type'], user_defined: bool, type_ref: str):
        self.kind = kind
        self.user_defined = user_defined
        self.type_ref = type_ref

class Compiler:
    definitions: dict[str, Types.Definition]
    ast: dict[str, AST.Expression]
    meta: dict[str, Meta]
    
    def __init__(self):
        self.definitions = {}
        self.ast = {}
        self.meta = {}
        Type = self.define_native_type('Type')
        Object = self.define_native_type('Object')
        String = self.define_native_type('String', extends=Object)
        Number = self.define_native_type('Number', extends=Object)
        Boolean = self.define_native_type('Boolean', extends=Object)
        self.define_native_edge(model=Type, name='$and', args=[Type], returns=Type)
        self.define_native_edge(model=Type, name='$or', args=[Type], returns=Type)
        self.define_native_edge(model=Type, name='$xor', args=[Type], returns=Type)
        self.define_native_edge(model=Type, name='$eq', args=[Object], returns=Type)
        self.define_native_edge(model=Type, name='$ne', args=[Object], returns=Type)
        self.define_native_edge(model=Type, name='$gt', args=[Object], returns=Type)
        self.define_native_edge(model=Type, name='$lt', args=[Object], returns=Type)
        self.define_native_edge(model=Type, name='$gte', args=[Object], returns=Type)
        self.define_native_edge(model=Type, name='$lte', args=[Object], returns=Type)
        self.define_native_edge(model=Type, name='$filter', args=[Boolean], returns=Type)
        self.define_native_edge(model=Object, name='$eq', args=[Object], returns=Boolean)
        self.define_native_edge(model=Object, name='$ne', args=[Object], returns=Boolean)
        self.define_native_edge(model=Boolean, name='$and', args=[Boolean], returns=Boolean)
        self.define_native_edge(model=Boolean, name='$or', args=[Boolean], returns=Boolean)
        self.define_native_edge(model=Boolean, name='$xor', args=[Boolean], returns=Boolean)
        self.define_native_edge(model=Number, name='$gt', args=[Number], returns=Boolean)
        self.define_native_edge(model=Number, name='$lt', args=[Number], returns=Boolean)
        self.define_native_edge(model=Number, name='$gte', args=[Number], returns=Boolean)
        self.define_native_edge(model=Number, name='$lte', args=[Number], returns=Boolean)
        self.define_native_edge(model=Number, name='$add', args=[Number], returns=Number)
        self.define_native_edge(model=Number, name='$sub', args=[Number], returns=Number)
        self.define_native_edge(model=Number, name='$mul', args=[Number], returns=Number)
        self.define_native_edge(model=Number, name='$div', args=[Number], returns=Number)
        self.define_native_edge(model=Number, name='$mod', args=[Number], returns=Number)
        self.define_native_edge(model=String, name='length', returns=Number)
        self.define_native_edge(model=String, name='$gt', args=[String], returns=Boolean)
        self.define_native_edge(model=String, name='$lt', args=[String], returns=Boolean)
        self.define_native_edge(model=String, name='$gte', args=[String], returns=Boolean)
        self.define_native_edge(model=String, name='$lte', args=[String], returns=Boolean)
        self.define_native_edge(model=String, name='$add', args=[String], returns=String)

    @property
    def edges(self) -> list[Types.Edge]:
        return [
            self.get_edge(ref)
            for ref, meta in self.meta.items()
            if meta.kind == 'edge' and meta.user_defined
        ]

    @property
    def types(self) -> list[Types.Type]:
        return [
            self.get_type(ref, include_edges=True)
            for ref, meta in self.meta.items()
            if meta.kind == 'type' and meta.user_defined
        ]

    def get_models(self) -> Types.Models:
        return {
            type_ref: self.get_type(type_ref, include_edges=True)
            for type_ref, meta in self.meta.items()
            if meta.kind == 'type' and meta.user_defined
        }
    
    def get_edges(self, type_ref: str) -> list[Types.Edge]:
        assert self.meta[type_ref].kind == 'type' 
        return [
            self.get_edge(edge_ref)
            for edge_ref, meta in self.meta.items()
            if meta.kind == 'edge' and meta.type_ref == type_ref
        ]

    def define_native_type(self, *args, **kwargs) -> Types.Type:
        typ = Types.Type(*args, **kwargs)
        self.definitions[typ.ref] = typ
        self.meta[typ.ref] = Meta(kind='type', user_defined=False, type_ref=typ.ref)
        return typ
    
    def define_native_edge(self, *args, **kwargs) -> Types.Edge:
        edge = Types.Edge(*args, **kwargs)
        self.definitions[edge.ref] = edge
        self.meta[edge.ref] = Meta(kind='edge', user_defined=False, type_ref=edge.model.ref)
        return edge
    
    def _save_ast(self, type_ref: str, ref: str, ast: AST.Definition):
        assert ref not in self.ast
        assert ref not in self.definitions
        self.ast[ref] = ast
        self.meta[ref] = Meta(
            kind='type' if isinstance(ast, AST.TypeDefinition) else 'edge',
            user_defined=True,
            type_ref=type_ref,
        )

    def read_edge(self, type_ref: str, ast: AST.EdgeDefinition) -> Compiler:
        self._save_ast(type_ref, type_ref + '.' + ast.name, ast)
        return self

    def read_type(self, ast: AST.TypeDefinition) -> Compiler:
        self._save_ast(ast.name, ast.name, ast)
        if isinstance(ast, AST.ModelDefinition):
            for edge_ast in ast.edges:
                self.read_edge(ast.name, edge_ast)
        return self
    
    def read_definitions(self, ast: AST.ModuleDefinitions) -> Compiler:
        for child in ast.children:
            self.read_type(child)
        return self

    def _get(self, ref: str) -> Types.Definition:
        if ref not in self.meta:
            raise KeyError(f'Unknown symbol `{ref}`')

        # Already compiled
        if ref in self.definitions:
            existing = self.definitions[ref]
            if existing is None:
                raise Exception(f'Possible circular reference for `{ref}`')
            return existing
    
        # Clear the ref from the table first, 
        # so that if the function calls itself
        # it will get a circular reference error
        self.definitions[ref] = None
        if self.meta[ref].kind == 'edge':
            self.definitions[ref] = self.compile_edge(self.ast[ref], self.get_type(self.meta[ref].type_ref))
        elif self.meta[ref].kind == 'type':
            self.definitions[ref] = self.compile_type(self.ast[ref])
        assert isinstance(self.definitions[ref], Types.Definition)
        return self.definitions[ref]

    def get_type(self, type_ref: str, include_edges=False) -> Types.Type:
        typ = self._get(type_ref)
        assert isinstance(typ, Types.Type)
        if include_edges:
            for edge in self.get_edges(type_ref):
                if edge.name not in typ.edges:
                    typ.edges[edge.name] = edge
                else:
                    assert typ.edges[edge.name] == edge
        return typ

    def get_edge(self, edge_ref: str) -> Types.Edge:
        edge = self._get(edge_ref)
        assert isinstance(edge, Types.Edge)
        return edge
    
    def lookup_edge(self, typ: Types.Type, name: str) -> Types.Edge:
        extended_type = typ
        ref = extended_type.ref + '.' + name
        while ref not in self.meta and extended_type.extends is not None:
            extended_type = extended_type.extends
            ref = extended_type.ref + '.' + name
        
        if ref not in self.meta:
            raise KeyError(f"Unknown edge `{typ.ref}.{name}`")
        
        return self.get_edge(ref)

    def compile_edge(self, ast: AST.EdgeDefinition, model: Types.Type):
        assert isinstance(ast, AST.EdgeDefinition)
        return Types.Edge(
            name=ast.name,
            model=model,
            nullable=ast.cardinality in ('?','*'),
            multiple=ast.cardinality in ('+','*'),
            loc=ast.meta,
            expr=self.compile_expression(ast.type, model),
        )
    
    def compile_type(self, ast: AST.TypeDefinition):
        assert isinstance(ast, AST.TypeDefinition)
        if isinstance(ast, AST.AliasDefinition):
            return Types.Type(
                ref=ast.name,
                loc=ast.meta,
                expr=self.compile_expression(ast.type, None),
            )
        if isinstance(ast, AST.ModelDefinition):
            return Types.Type(
                ref=ast.name,
                indexes=ast.indexes,
                loc=ast.meta,
                extends=self.get_type('Object'),
            )
        raise Exception('Unknown TypeDefinition')
    
    def compile_expression(self, ast: AST.Expression, typ: Optional[Types.Type]) -> Types.Expression:
        assert isinstance(ast, AST.Expression)
        if isinstance(ast, AST.Identifier):
            if ast.kind == 'type':
                return Types.TypeRefExpression(
                    type=self.get_type(ast.name),
                    loc=ast.meta,
                    returns=self.get_type('Type'),
                )
            if ast.kind == 'edge':
                edge = self.lookup_edge(typ, ast.name)
                return Types.EdgeRefExpression(
                    edge=edge,
                    loc=ast.meta,
                )
        elif isinstance(ast, AST.LiteralExpression):
            if type(ast.value) is str:
                typ = self.get_type('String')
            elif type(ast.value) is bool:
                typ = self.get_type('Boolean')
            elif isinstance(ast.value, (int, float)):
                typ = self.get_type('Number')
            else:
                raise Exception()
            return Types.LiteralExpression(type=typ, value=ast.value, loc=ast.meta)
        elif isinstance(ast, AST.Operation):
            assert len(ast.children) >= 1
            expr = self.compile_expression(ast.children[0], typ)
            if ast.name == 'filter':
                assert len(ast.children) <= 2
                if len(ast.children) == 2:
                    assert expr.is_type()
                    filter = self.compile_expression(ast.children[1], expr.get_context())
                    expr = Types.CallExpression(
                        bound=expr,
                        args=[filter],
                        edge=self.get_edge('Type.$filter'),
                        loc=ast.meta,
                    )
            elif ast.name == 'dot':
                assert len(ast.children) >= 2
                for child in ast.children[1:]:
                    expr = self.compile_expression(child, expr.get_context())
            else:
                for child in ast.children[1:]:
                    expr = Types.CallExpression(
                        bound=expr,
                        args=[
                            self.compile_expression(child, typ)
                        ],
                        edge=self.lookup_edge(expr.returns, '$' + ast.name),
                        loc=ast.meta,
                    )
            return expr
        else:
            raise Exception('Unknown Expression')