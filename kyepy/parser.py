from lark import Lark, Visitor, Tree
from pathlib import Path
from kye_transformer import TreeToKye

DIR = Path(__file__).parent

with open(DIR / 'grammar.lark') as f:
    grammar = f.read()

parser = Lark(grammar, start='start', parser='lalr')

class Parent(Visitor):
    def __default__(self, tree):
        for subtree in tree.children:
            if isinstance(subtree, Tree):
                assert not hasattr(subtree, 'parent')
                subtree.parent = tree

transformer = TreeToKye()

if __name__ == '__main__':
    import sys
    # file_path = sys.argv[1]
    file_path = DIR / '../examples/yellow.kye'
    with open(file_path) as f:
        text = f.read()
    tree = parser.parse(text)
    print(tree.pretty())
    ast = transformer.transform(tree)
    print(ast)