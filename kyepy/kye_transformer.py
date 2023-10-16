from kye_ast import *
from lark import Transformer, visitors

@visitors.v_args(inline=True)
class TreeToKye(Transformer):    
    def ESCAPED_STRING(self, s):
        return s[1:-1]
    
    def SIGNED_NUMBER(self, n):
        return float(n)
    
    @visitors.v_args(inline=False)
    def index(self, edges):
        return Index(edges=edges)

    def type_index(self, typ, index):
        return TypeIndex(typ=TypeRef(name=typ), index=index)
    
    def type_ref(self, name):
        return TypeRef(name=name)
    
    def TYPE(self, n):
        return n.value
    
    def EDGE(self, n):
        return n.value
    
    def CARDINALITY(self, n):
        return n.value
    
    def edge(self, name, typ=None, cardinality=None):
        return Edge(name=name, typ=typ, cardinality=cardinality)
    
    def alias(self, name, typ):
        return TypeAlias(name=name, typ=typ)
    
    @visitors.v_args(inline=False)
    def model(self, children):
        return Model(
            name=children[0],
            indexes=[child for child in children[1:] if isinstance(child, Index)],
            edges=[child for child in children[1:] if isinstance(child, Edge)],
        )
    
    @visitors.v_args(inline=False)
    def start(self, definitions):
        return Script(definitions=definitions)