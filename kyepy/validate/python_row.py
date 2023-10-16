from kyepy.kye_ast import *

def validate_python(ast, data):
    if isinstance(ast, Model):
        # TODO: Allow model to just be the index value without the dictionary model?
        assert type(data) is dict
        keys = list({idx for idxs in ast.indexes for idx in idxs.edges})
        for key_edge in keys:
            if key_edge not in data:
                raise KeyError(f'"{key_edge}" is required')

        for edge in ast.edges:
            if edge.name not in data:
                continue

            if data[edge.name] is None:
                if edge.cardinality in ('*', '?'):
                    continue
                else:
                    raise ValueError(f'"{edge.name}" cannot be null')
            
            # TODO: Allow list of models to use a map of index to model
            # or maybe should have a Map type to explicitly allow those situations...
            if type(data[edge.name]) is list:
                if edge.cardinality in ('?', '!') and len(data[edge.name]) > 1:
                    raise ValueError(f'"{edge.name}" cannot have multiple values')
                if edge.cardinality in ('+',) and len(data[edge.name]) == 0:
                    raise ValueError(f'"{edge.name}" cannot be an empty list')
                for item in data[edge.name]:
                    validate_python(edge.typ, item)
            else:
                validate_python(edge.typ, data[edge.name])
    
    elif isinstance(ast, TypeRef):
        if ast.name == 'String':
            if type(data) is not str:
                raise ValueError(f'"{data}" is not a string')
        
        elif ast.name == 'Number':
            if not isinstance(data, (int, float)):
                raise ValueError(f'"{data}" is not a number')
        
        else:
            validate_python(ast.resolve(), data)
        
    # TODO: allow TypeIndex to just be the index value without the dictionary model
    elif isinstance(ast, (TypeAlias, TypeIndex)):
        validate_python(ast.typ, data)