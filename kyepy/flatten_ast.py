from kyepy.kye_ast import *

def define_models(node: AST, models):
    
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
        edge = {
            'type': node.typ.type_ref,
        }
        if node.cardinality in ('?', '*'):
            edge['nullable'] = True
        if node.cardinality in ('+', '*'):
            edge['multiple'] = True

        models[node.type_ref]['edges'][node.name] = edge
    
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
        define_models(child, models)

    return models

def simplify_models(models):
    simplify = {}
    for ref, model in models.items():
        if set(model.keys()) == {'extends'}:
            simplify[ref] = model['extends']
        elif set(model.keys()) == {'extends','indexes'}:
            assert len(model['indexes']) == 1
            if tuple(models[model['extends']]['indexes'][0]) == tuple(model['indexes'][0]):
                simplify[ref] = model['extends']

    for model in models.values():
        for edge in model.get('edges',{}).values():
            if edge.get('type') in simplify:
                edge['type'] = simplify[edge['type']]
    
    for ref in simplify.keys():
        del models[ref]

def flatten_ast(ast: AST):
    models = {}
    define_models(ast, models)
    simplify_models(models)
    return models