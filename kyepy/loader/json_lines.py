import json
from pathlib import Path
from kyepy.dataset import Type, Edge, Dataset, TYPE_REF
from typing import Any

def normalize_value(typ: Type, data: Any):
    if typ.issubclass('Struct'):
        # TODO: better error handling
        assert type(data) is dict
        return {
            edge_name: normalize_edge(edge, data.get(edge_name))
            for edge_name, edge in typ.edges.items()
                if data.get(edge_name) is not None
        }

    assert type(data) is not dict
    return str(data)

def normalize_edge(edge: Edge, data: Any):
    """
    Handle zero or many values, calling `normalize_value`
    on each singular item.
    """
    if edge.multiple:
        if data is None:
            return []
        if type(data) is not list:
            data = [ data ]
        return [
            normalize_value(edge._type, item) for item in data
            if item is not None
        ]
    
    assert type(data) is not list

    if data is None:
        return None

    return normalize_value(edge._type, data)

def normalize_json(typ: Type, data: Any):
    if type(data) is not list:
        data = [ data ]
    return [ normalize_value(typ, item) for item in data ]


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
        for row in normalize_json(self.models[type_ref], data):
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