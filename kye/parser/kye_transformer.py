from typing import Any
from kye.parser.kye_ast import *
from lark import Token, Tree

OPERATORS_MAP = {
    'or_exp': '|',
    'xor_exp': '^',
    'and_exp': '&',
    'dot_exp': '.',
    'filter_exp': '[]',
    'is_exp': 'is',
}

def tokens_to_ast(token: Union[Tree, Token], script: str):

    if isinstance(token, Token):
        kind = token.type
        meta = token
        value = token.value
        children = [ value ]
    elif isinstance(token, Tree):
        kind = token.data
        meta = token.meta
        children = [tokens_to_ast(child, script) for child in token.children]
    
    meta = TokenPosition(
        line=meta.line,
        column=meta.column,
        end_line=meta.end_line,
        end_column=meta.end_column,
        start_pos=meta.start_pos,
        end_pos=meta.end_pos,
        text=script[meta.start_pos:meta.end_pos],
    )

    # Lark prefixes imported rules with '<module_name>__'
    # we will just make sure that we don't have any name conflicts
    # across grammar files and remove the prefixes so that we can
    # use the same transformer independently of how the grammar
    # was imported
    if '__' in kind:
        kind = kind.split('__')[-1]
        assert kind != '', 'Did not expect rule name to end with a double underscore'

    if kind == 'SIGNED_NUMBER':
        return float(value)
    if kind == 'ESCAPED_STRING':
        return value[1:-1]
    if kind == 'identifier':
        return Identifier(name=children[0], meta=meta)
    if kind == 'literal':
        return LiteralExpression(value=children[0], meta=meta)
    if kind in ('comp_exp', 'mult_exp', 'add_exp'):
        return Operation(op=children[1], children=[children[0], children[2]], meta=meta)
    if kind in OPERATORS_MAP:
        return Operation(op=OPERATORS_MAP[kind], children=children, meta=meta)
    if kind == 'unary_expression':
        Operation(op=children[0], children=[children[1]], meta=meta)

    if kind == 'alias_def':
        name, typ = children
        return AliasDefinition(name=name, type=typ, meta=meta)

    if kind == 'edge_def':
        if len(children) == 3:
            name, cardinality, typ = children
        elif len(children) == 2:
            name, typ = children
            cardinality = None
        else:
            raise ValueError('Invalid edge definition')
        
        return EdgeDefinition(name=name, type=typ, cardinality=cardinality, meta=meta)

    if kind == 'index':
        return children

    if kind == 'model_def':
        indexes = []
        edges = []
        subtypes = []
        for child in children[1:]:
            if isinstance(child, EdgeDefinition):
                edges.append(child)
            elif isinstance(child, TypeDefinition):
                subtypes.append(child)
            else:
                assert type(child) is list
                indexes.append(child)

        return ModelDefinition(
            name=children[0],
            indexes=indexes,
            edges=edges,
            subtypes=subtypes,
            meta=meta
        )

    if kind == 'definitions':
        return ModuleDefinitions(children=children, meta=meta)

    if isinstance(token, Token):
        return value
    else:
        raise Exception(f'Unknown rule: {kind}')


def globalize_names(ast: AST, path = tuple(), type_name_map = dict()):

    def rename_identifiers(ast: Expression, type_name_map: dict[str, str]):
        if isinstance(ast, Operation) and ast.name == 'dot':
            # Only rename the first child for the dot operator,
            # because the following children have a different context
            rename_identifiers(ast.children[0], type_name_map)
            return
        if isinstance(ast, Identifier) and ast.name in type_name_map:
            ast.name = type_name_map[ast.name]

        for child in ast.children:
            rename_identifiers(child, type_name_map)

    if isinstance(ast, Definition):
        path += (ast.name,)
        if isinstance(ast, TypeDefinition):
            ast.name = '.'.join(path)
        elif isinstance(ast, EdgeDefinition):
            ast._ref = '.'.join(path)
            rename_identifiers(ast, type_name_map)
    if isinstance(ast, ContainedDefinitions):
        local = {**type_name_map}
        for child in ast.children:
            if isinstance(child, TypeDefinition):
                local[child.name] = '.'.join(path + (child.name,))
        for child in ast.children:
            globalize_names(child, path, local)

def unnest_subtypes(ast: AST):
    def collect_types(ast: AST):
        if isinstance(ast, TypeDefinition):
            yield ast
        if isinstance(ast, ContainedDefinitions):
            for child in ast.children:
                yield from collect_types(child)
    
    if isinstance(ast, ModuleDefinitions):
        ast.children = list(collect_types(ast))

def transform(token: Union[Tree, Token], script: str):
    ast = tokens_to_ast(token, script)
    globalize_names(ast)
    unnest_subtypes(ast)
    return ast