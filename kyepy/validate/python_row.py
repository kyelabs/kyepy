# from kyepy.kye_ast import *
from kyepy.dataset import Type, Edge

def validate_edge(model, edge_name, edge_value):
    if edge_value is None:
        return
    if type(edge_value) is not list:
        edge_value = [ edge_value ]
    for val in edge_value:
        validate_python(model.edges[edge_name]._type, val)

def validate_python(model, data):
    for parent_type in model.inheritance_chain:
        name = parent_type.name

        if name == 'Number':
            if not isinstance(data, (int, float)):
                raise ValueError(f'"{data}" is not a number')
        
        if name == 'String':
            if type(data) is not str:
                raise ValueError(f'"{data}" is not a string')
            validate_edge(model, 'length', len(data))
        
        if name == 'Boolean':
            if type(data) is not bool:
                raise ValueError(f'"{data}" is not a boolean')
        
        if name == 'Struct':
            if type(data) is not dict:
                raise ValueError(f'"{data}" is not a struct')
            for edge_name, edge in model.edges.items():
                validate_edge(model, edge_name, data.get(edge_name))
        
        if name == 'Model':
            def has_any_index():
                def has_index(index):
                    for edge_name in index:
                        if edge_name not in data:
                            return False
                    return True
                
                for index in model.indexes:
                    if has_index(index):
                        return True
                return False

            if not has_any_index():
                raise ValueError(f'"{data}" is missing index fields')