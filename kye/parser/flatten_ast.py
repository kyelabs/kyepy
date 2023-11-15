from kye.parser.kye_ast import *

def define_models(node: AST, models):
    
    if isinstance(node, ModelDefinition):
        assert node.type_ref not in models
        models[node.type_ref] = {
            'name': node.name,
            'indexes': [idx.edges for idx in node.indexes],
            'edges': {},
        }
    
    elif isinstance(node, EdgeDefinition):
        assert node.type_ref in models
        assert node.type_ref not in models[node.type_ref]['edges']
        edge = {
            'type': node.type.type_ref,
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

def get_models_to_simplify(models):
    simplify = {}
    for ref, model in models.items():
        if set(model.keys()) == {'extends'}:
            simplify[ref] = model['extends']
        elif set(model.keys()) == {'extends','indexes'}:
            assert len(model['indexes']) == 1
            referenced_indexes = models[model['extends']]['indexes']
            if len(referenced_indexes) == 1 and tuple(referenced_indexes[0]) == tuple(model['indexes'][0]):
                simplify[ref] = model['extends']
    
    return simplify

def update_models(models, simplify):
    for model in models.values():
        if 'extends' in model and model['extends'] in simplify:
            model['extends'] = simplify[model['extends']]
        for edge in model.get('edges',{}).values():
            if edge.get('type') in simplify:
                edge['type'] = simplify[edge['type']]

    for ref in simplify.keys():
        if ref in models:
            del models[ref]
    
EBRAKE = 10

def simplify_models(models):
    simplify = {}
    ebrake = EBRAKE
    while ebrake == EBRAKE or (len(to_simplify) > 0 and ebrake > 0):
        to_simplify = get_models_to_simplify(models)
        simplify.update(to_simplify)
        update_models(models, simplify)
        ebrake -= 1
    
    assert ebrake > 0, "Simplify loop ebrake triggered"

def flatten_ast(ast: AST):
    models = {}
    define_models(ast, models)
    simplify_models(models)
    return models