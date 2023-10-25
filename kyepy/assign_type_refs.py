from kyepy.kye_ast import *

def get_defined_type_ref(node: AST):
    if isinstance(node, Model):
        return node.scope.path

def get_propagated_type_ref(node: AST):
    if isinstance(node, (Edge, TypeAlias)):
        return node.type_ref + '.' + node.name
    return node.type_ref

def assign_type_refs(node: AST, parent_type_ref=None):
    type_ref = get_defined_type_ref(node) or parent_type_ref

    assert type_ref is not None or isinstance(node, Script), 'Type reference not found'
    node.type_ref = type_ref
    
    for child in node.children:
        assign_type_refs(child, parent_type_ref=get_propagated_type_ref(node))