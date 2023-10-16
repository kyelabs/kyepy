from kyepy.kye_ast import *

def to_json_schema(ast):
    # TODO: don't assume using last definition as root
    # instead don't allow passing in Script, instead pass in Model,
    # and use ast traversal to find all definitions
    if isinstance(ast, Script):
        last_defn = {}
        if len(ast.definitions) > 0:
            last_defn = to_json_schema(ast.definitions[-1])
            last_defn['title'] = ast.definitions[-1].name
        return {
            '$schema': 'http://json-schema.org/draft-07/schema#',
            'definitions': {
                defn.name: to_json_schema(defn) for defn in ast.definitions[:-1]
            },
            **last_defn,
        }
    
    if isinstance(ast, Model):

        json_schema = {
            'type': 'object',
            'properties': {},
        }

        # Require fields in indexes
        # TODO: support only requiring a single index for type calls?
        required = list({idx for idxs in ast.indexes for idx in idxs.edges})
        if len(required) > 0:
            json_schema['required'] = required
        
        # Add edges to properties
        for edge in ast.edges:
            if edge.cardinality in ('*', '+'):
                json_schema['properties'][edge.name] = {
                    'type': 'array',
                    'items': to_json_schema(edge.typ),
                }
                if edge.cardinality == '+':
                    json_schema['properties'][edge.name]['minItems'] = 1
            elif edge.cardinality == '?':
                json_schema['properties'][edge.name] = {
                    'oneOf': [
                        to_json_schema(edge.typ),
                        { 'type': 'null' },
                    ]
                }
            else:
                json_schema['properties'][edge.name] = to_json_schema(edge.typ)
        
        return json_schema
    
    if isinstance(ast, TypeRef):
        if ast.name == 'String':
            return {'type': 'string'}
    
        if ast.name == 'Number':
            return {'type': 'number'}
        
        return { '$ref': f'#/definitions/{ast.name}' }

    if isinstance(ast, (TypeAlias, TypeIndex)):
        return to_json_schema(ast.typ)
    
    raise Exception('Unknown AST node', ast)