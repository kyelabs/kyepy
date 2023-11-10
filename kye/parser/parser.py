from lark import Lark
from pathlib import Path
from kye.parser.kye_transformer import TreeToKye
from lark import Transformer, Visitor, Tree, visitors

DIR = Path(__file__).parent

with open(DIR / 'grammar.lark') as f:
    grammar = f.read()

parser = Lark(
    grammar,
    start='start',
    parser='lalr',
    strict=True,
    propagate_positions=True
)

transformer = TreeToKye()
class Parser:
    def __init__(self, text):
        self.text = text
        self.tree = parser.parse(text)
        self.ast = transformer.transform(self.tree)
        print('hi')

    @staticmethod
    def from_text(text):
        return Parser(text)
    
    @staticmethod
    def from_file(file_path):
        with open(file_path) as f:
            text = f.read()
        return Parser(text)

    def print_tree(self):
        print(self.tree.pretty())