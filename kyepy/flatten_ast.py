from kyepy.kye_ast import *

def flatten_ast(node: AST, models={}):
    
    if isinstance(node, Model):
        assert node.type_ref not in models
        models[node.type_ref] = {
            'name': node.name,
            'indexes': [idx.edges for idx in node.indexes],
            'edges': {},
        }
    
    elif isinstance(node, Edge):
        assert node.type_ref in models
        assert node.type_ref not in models[node.type_ref]['edges']
        models[node.type_ref]['edges'][node.name] = {
            'type': node.typ.type_ref,
            'nullable': node.cardinality in ('?', '*'),
            'multiple': node.cardinality in ('+', '*'),
        }
    
    elif isinstance(node, TypeRef):
        assert node.type_ref not in models
        referenced_type = node.scope[node.name]
        extends = referenced_type.type_ref if isinstance(referenced_type, AST) else node.name

        models[node.type_ref] = {
            'extends': extends,
        }
        
        if node.index:
            models[node.type_ref]['indexes'] = [ node.index.edges ]
    
    for child in node.children:
        flatten_ast(child, models)

    return models