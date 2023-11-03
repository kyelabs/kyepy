from kyepy.kye_ast import *
from lark import Transformer, visitors

@visitors.v_args(meta=True)
class TreeToKye(Transformer):    
    def ESCAPED_STRING(self, n):
        return n[1:-1]
    
    def SIGNED_NUMBER(self, n):
        return float(n)
    
    def index(self, meta, children):
        return Index(edges=children, meta=meta)
    
    def type_ref(self, meta, children):
        return TypeRef(
            name=children[0],
            index=children[1] if len(children) > 1 and isinstance(children[1], Index) else None,
            meta=meta
        )
    
    def TYPE(self, n):
        return n.value
    
    def EDGE(self, n):
        return n.value
    
    def CARDINALITY(self, n):
        return n.value
    
    def edge(self, meta, children):
        name = children[0]
        typ = children[1] if len(children) > 1 else None
        cardinality = children[2] if len(children) > 2 else None
        return Edge(name=name, typ=typ, cardinality=cardinality, meta=meta)
    
    def alias(self, meta, children):
        name, typ = children
        return TypeAlias(name=name, typ=typ, meta=meta)
    
    def model(self, meta, children):
        return Model(
            name=children[0],
            indexes=[child for child in children[1:] if isinstance(child, Index)],
            edges=[child for child in children[1:] if isinstance(child, Edge)],
            meta=meta,
        )
    
    def start(self, meta, children):
        return Script(children=children, meta=meta)