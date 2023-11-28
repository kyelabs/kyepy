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

def display(env: RootEnvironment):
    FORMAT = '{:<15} {:<40} {}'
    print(FORMAT.format('Name', 'Type', 'AST'))
    print('-'*100)

    def display_child(env, depth=0):
        print(FORMAT.format(
            '  ' * depth + env.name,
            repr(env.type),
            repr(env.evaluator.ast),
        ))
        for child in env.local.values():
            display_child(child, depth + 1)
    
    for child in env.local.values():
        display_child(child)

def kye_to_ast(text):
    ast = parse_definitions(text)

    GLOBAL_ENV = RootEnvironment()
    GLOBAL_ENV.define('String', lambda ast,env: Type('String'))
    GLOBAL_ENV.lookup('String').define('length', lambda ast, env: env.lookup('Number').type)
    GLOBAL_ENV.define('Number', lambda ast,env: Type('Number'))
    GLOBAL_ENV.apply_ast(ast)

    display(GLOBAL_ENV)
    return ast

def compile(text):
    ast = kye_to_ast(text)
    raw_models = flatten_ast(ast)
    return raw_models