from kye_ast import *
from lark import Transformer, visitors

@visitors.v_args(inline=True)
class TreeToKye(Transformer):    
    def string(self, s):
        return s[1:-1]
    
    def number(self, n):
        return float(n)
    
    def index(self, *ids):
        return list(ids)

    def type_const(self, value):
        return Const(value=value)

    def type_index(self, typ, index):
        return Index(name=typ, index=index)
    
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
    
    # def edges(self, *edges):
    #     return list(edges)
    
    # def indexes(self, *indexes):
    #     return list(indexes)
    
    def alias(self, name, typ):
        return Alias(name=name, typ=typ)
    
    def model(self, name, indexes, edges):
        return Model(name=name, indexes=indexes, edges=edges)
    
    def start(self, *definitions):
        return Script(definitions=definitions)