from kye.parser.kye_ast import *
from lark import Transformer, visitors

def binary_expression(_, meta, children):
    return Operation(op=children[1].value, children=[children[0], children[2]], meta=meta)

def binary_expression_using(op):
    def _binary_expression(_, meta, children):
        return Operation(op=op, children=children, meta=meta)
    return _binary_expression

@visitors.v_args(meta=True)
class TreeToKye(Transformer):
    def ESCAPED_STRING(self, n):
        return n[1:-1]
    
    def SIGNED_NUMBER(self, n):
        return float(n)
    
    def identifier(self, meta, children):
        return Identifier(name=children[0].value, meta=meta)
    
    def literal(self, meta, children):
        return LiteralExpression(value=children[0], meta=meta)

    comp_exp = binary_expression
    mult_exp = binary_expression
    add_exp = binary_expression
    or_exp = binary_expression_using('|')
    xor_exp = binary_expression_using('^')
    and_exp = binary_expression_using('&')
    dot_exp = binary_expression_using('.')
    filter_exp = binary_expression_using('[]')
    
    def unary_expression(self, meta, children):
        return Operation(op=children[0].value, children=[children[1]], meta=meta)
        
    def edge_def(self, meta, children):
        cardinality = None
        if len(children) == 3:
            name, cardinality, typ = children
            cardinality = cardinality.value
        elif len(children) == 2:
            name, typ = children
        else:
            raise ValueError('Invalid edge definition')
        
        return EdgeDefinition(name=name.value, typ=typ, cardinality=cardinality, meta=meta)
    
    def alias_def(self, meta, children):
        name, typ = children
        return AliasDefinition(name=name, typ=typ, meta=meta)
    
    def model_def(self, meta, children):
        name = children[0].value
        indexes = []
        edges = []
        for child in children[1:]:
            if isinstance(child, EdgeDefinition):
                edges.append(child)
            else:
                assert child.data.value == 'index'
                indexes.append([idx.value for idx in child.children])

        return ModelDefinition(name=name,indexes=indexes,edges=edges, meta=meta)
    
    def definitions(self, meta, children):
        return Definitions(children=children, meta=meta)