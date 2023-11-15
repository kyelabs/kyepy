from lark import Lark
from lark.load_grammar import FromPackageLoader
from pathlib import Path
from kye.parser.kye_transformer import transform
from kye.parser.assign_scopes import assign_scopes, Scope
from kye.parser.assign_type_refs import assign_type_refs
from kye.parser.flatten_ast import flatten_ast
from kye.dataset import Models

GRAMMAR_DIR = Path(__file__).parent / 'grammars'

GLOBAL_SCOPE = Scope(name=None, parent=None)
for global_type in Models.globals.keys():
    GLOBAL_SCOPE[global_type] = '<built-in type>'

def get_parser(grammar_file, start_rule):
    def parse(text):
        parser = Lark(
            f"""
            %import {grammar_file}.{start_rule}
            %import tokens (WS, COMMENT)
            %ignore WS
            %ignore COMMENT
            """,
            start=start_rule,
            parser='lalr',
            strict=True,
            propagate_positions=True,
            import_paths=[FromPackageLoader(__name__, ('grammars',))],
        )
        tree = parser.parse(text)
        ast = transform(tree, text)
        return ast
    return parse

parse_definitions = get_parser('definitions', 'definitions')
parse_expression = get_parser('expressions', 'exp')

def print_ast(ast):
    FORMAT = '{:<20} {:<20} {}'
    print(FORMAT.format('Scope', 'Type', 'Node'))
    print('-'*80)
    for path, node in ast.traverse():
        print(FORMAT.format(
            getattr(node.scope, 'path', '') or '',
            node.type_ref or '',
            '    '*(len(path)-1) + repr(node))
        )

def kye_to_ast(text):
    ast = parse_definitions(text)
    assign_scopes(ast, scope=GLOBAL_SCOPE)
    # assign_type_refs(ast)
    print_ast(ast)
    return ast

def compile(text):
    ast = kye_to_ast(text)
    raw_models = flatten_ast(ast)
    return raw_models