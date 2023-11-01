import json
from pathlib import Path
from kyepy.dataset import Type, Edge, Dataset, TYPE_REF
from typing import Any

def normalize_value(typ: Type, data: Any):
    if data is None:
        return None

    # TODO: reshape id maps { [id]: { ... } } to [ { id, ... } ]
    # not sure if we want to do that auto-magically or have it explicitly
    # defined as part of the schema
    if typ.issubclass('Struct'):
        # TODO: better error handling, i.e trace location in data
        # so that we can report the location of the error
        assert type(data) is dict

        edges = {}
        for edge_name, edge in typ.edges.items():
            if edge_name not in data:
                continue

            val = normalize_edge(edge, data.get(edge_name))
            if val is not None:
                edges[edge_name] = val

        if len(edges) == 0:
            return None
        
        return edges

    assert type(data) is not dict
    return str(data)

def normalize_values(typ: Type, data: Any):
    if data is None:
        return None

    if type(data) is not list:
        data = [ data ]

    values = []
    for item in data:
        val = normalize_value(typ, item)
        if val is not None:
            values.append(val)
    
    if len(values) == 0:
        return None
    
    return values

def normalize_edge(edge: Edge, data: Any):
    if data is None:
        return None

    if edge.multiple:
        return normalize_values(edge._type, data)
    
    assert type(data) is not list
    return normalize_value(edge._type, data)

class JsonLineLoader:
    
    def __init__(self, models: Dataset, directory: str):
        self.models = models
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        assert self.directory.is_dir()
        self.files = {}
        self._is_closed = False
    
    def _get_file_path(self, type_ref: TYPE_REF):
        return self.directory / f'{type_ref}.json'

    def _get_file_handler(self, type_ref: TYPE_REF):
        if type_ref not in self.files:
            self.files[type_ref] = self._get_file_path(type_ref).open('w', encoding='utf-8')
        return self.files[type_ref]

    def write(self, type_ref: TYPE_REF, data: Any):
        assert not self._is_closed, 'Cannot write to a closed loader'
        f = self._get_file_handler(type_ref)
        assert type_ref in self.models
        for row in normalize_values(self.models[type_ref], data):
            json.dump(row, f)
            f.write('\n')

    def close(self):
        self._is_closed = True
        for file in self.files.values():
            file.close()
    
    def load_duckdb(self, con):
        assert self._is_closed, 'Cannot load to duckdb until the loader is closed'
        assert len(self.files) > 0, 'Cannot load to duckdb until at least one model has been written'
        for type_ref, file in self.files.items():
            con.read_json(file.name).to_table('"' + type_ref + '"')
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()