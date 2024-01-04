import json
from pathlib import Path
from kye.types import Type, EDGE
from typing import Any
from duckdb import DuckDBPyConnection, DuckDBPyRelation
import re

DIR = Path(__file__).parent.parent.parent / 'data'
DIR.mkdir(parents=True, exist_ok=True)
assert DIR.is_dir()

def normalize_value(typ: Type, data: Any):
    if data is None:
        return None

    # TODO: reshape id maps { [id]: { ... } } to [ { id, ... } ]
    # not sure if we want to do that auto-magically or have it explicitly
    # defined as part of the schema
    if typ.has_index:
        # TODO: better error handling, i.e trace location in data
        # so that we can report the location of the error
        assert type(data) is dict

        edges = {}
        for edge in typ.edges:
            if edge not in data:
                continue

            val = normalize_edge(typ, edge, data.get(edge))
            if val is not None:
                edges[edge] = val
        
        missing_indexes = [key for key in typ.index if key not in edges]
        assert len(missing_indexes) == 0, f'Missing indexes for {repr(typ)}: {",".join(missing_indexes)}'
        
        if len(edges) == 0:
            return None
        
        return edges

    assert type(data) is not dict

    if type(data) is float:
        return re.sub(r'\.0$', '', str(data))

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

def normalize_edge(typ: Type, edge: EDGE, data: Any):
    if data is None:
        return None

    if typ.allows_multiple(edge):
        return normalize_values(typ.get_edge(edge), data)
    
    assert type(data) is not list
    return normalize_value(typ.get_edge(edge), data)

def from_json(typ: Type, data: list[dict], con: DuckDBPyConnection) -> DuckDBPyRelation:
    file_path = DIR / f'{typ.ref}.jsonl'

    with file_path.open('w', encoding='utf-8') as f:
        for row in normalize_values(typ, data):
            json.dump(row, f)
            f.write('\n')
    
    return con.read_json(str(file_path))