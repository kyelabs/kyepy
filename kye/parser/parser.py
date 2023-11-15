from lark import Lark
from pathlib import Path
from kye.parser.kye_transformer import TreeToKye
from kye.parser.assign_scopes import assign_scopes, Scope
from kye.parser.assign_type_refs import assign_type_refs
from kye.parser.flatten_ast import flatten_ast
from kye.dataset import Models

DIR = Path(__file__).parent

with open(DIR / 'grammar.lark') as f:
    grammar = f.read()

GLOBAL_SCOPE = Scope(name=None, parent=None)
for global_type in Models.globals.keys():
    GLOBAL_SCOPE[global_type] = '<built-in type>'

parser = Lark(
    grammar,
    start='definitions',
    parser='lalr',
    strict=True,
    propagate_positions=True
)

transformer = TreeToKye()

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
    tree = parser.parse(text)
    ast = transformer.transform(tree)
    assign_scopes(ast, scope=GLOBAL_SCOPE)
    assign_type_refs(ast)
    print_ast(ast)
    return ast

def compile(text):
    ast = kye_to_ast(text)
    raw_models = flatten_ast(ast)
    return raw_models