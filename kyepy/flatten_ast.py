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
            referenced_indexes = models[model['extends']]['indexes']
            if len(referenced_indexes) == 1 and tuple(referenced_indexes[0]) == tuple(model['indexes'][0]):
                simplify[ref] = model['extends']

    for model in models.values():
        if 'extends' in model and model['extends'] in simplify:
            model['extends'] = simplify[model['extends']]
        for edge in model.get('edges',{}).values():
            if edge.get('type') in simplify:
                edge['type'] = simplify[edge['type']]
    
    for ref in simplify.keys():
        del models[ref]
    
    return len(simplify)

def flatten_ast(ast: AST):
    models = {}
    define_models(ast, models)
    ebrake = 10
    while simplify_models(models) != 0 and ebrake > 0:
        ebrake -= 1
    assert ebrake > 0, "Simplify loop ebrake triggered"
    return models