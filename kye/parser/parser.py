from lark import Lark
from lark.load_grammar import FromPackageLoader
from pathlib import Path
from kye.parser.kye_transformer import transform
from kye.parser.flatten_ast import flatten_ast
from kye.parser.environment import RootEnvironment
from kye.parser.types import Type

GRAMMAR_DIR = Path(__file__).parent / 'grammars'

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
            '', # getattr(node._env, 'global_name', '') or '',
            '', # node.type_ref or '',
            '    '*(len(path)-1) + repr(node))
        )

def kye_to_ast(text):
    ast = parse_definitions(text)

    GLOBAL_ENV = RootEnvironment()
    GLOBAL_ENV.define('String', lambda ast,env: Type('String'))
    GLOBAL_ENV.lookup('String').define('length', lambda ast, env: env.lookup('Number').type)
    GLOBAL_ENV.define('Number', lambda ast,env: Type('Number'))
    GLOBAL_ENV.apply_ast(ast)

    print_ast(ast)
    print(GLOBAL_ENV.get_child('String').lookup('length').type)
    return ast

def compile(text):
    ast = kye_to_ast(text)
    raw_models = flatten_ast(ast)
    return raw_models