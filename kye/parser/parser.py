from lark import Lark
from lark.load_grammar import FromPackageLoader
from pathlib import Path
from kye.parser.kye_transformer import transform

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
            # strict=True,
            propagate_positions=True,
            import_paths=[FromPackageLoader(__name__, ('grammars',))],
        )
        tree = parser.parse(text)
        ast = transform(tree, text)
        return ast
    return parse

parse_definitions = get_parser('definitions', 'definitions')
parse_expression = get_parser('expressions', 'exp')