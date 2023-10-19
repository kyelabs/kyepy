from kyepy.kye_ast import *


def flatten_python_row(ast, data, loader):
    # If inspecting a model return an dict of the model's index values
    if isinstance(ast, Model):
        assert type(data) is dict
        row = {
            edge.name: flatten_python_row(edge, data[edge.name], loader)
            for edge in ast.edges if data.get(edge.name) is not None
        }

        loader.write(ast, row)

        # TODO: probably only need to return the values of the first index
        # or maybe the smallest index? Just returning everything for now
        index = {
            key_edge: row[key_edge]
            for key_edge in ast.get_key_names() if key_edge in data
        }
        return index
    
    if isinstance(ast, Edge):
        assert data is not None
        # Use the first item if the cardinality is non-plural
        if type(data) is list and ast.cardinality in ('?', '!'):
            data = data[0] if len(data) >= 1 else None
        
        # Convert to list if the cardinality is plural
        elif type(data) is not list and ast.cardinality in ('*', '+'):
            data = [data]
        
        if type(data) is list:
            return [flatten_python_row(ast.typ, item, loader) for item in data]
        else:
            return flatten_python_row(ast.typ, data, loader)

    if isinstance(ast, TypeRef):
        if ast.name == 'String':
            # TODO: might want to convert all values to strings in the future
            assert isinstance(data, str)
            return data
        
        elif ast.name == 'Number':
            assert isinstance(data, (int, float))
            return data
        
        else:
            return flatten_python_row(ast.resolve(), data, loader)
    
    if isinstance(ast, (TypeAlias, TypeIndex)):
        return flatten_python_row(ast.typ, data, loader)