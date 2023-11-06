from duckdb import DuckDBPyRelation
from kyepy.dataset import Type, DefinedType, Edge, TYPE_REF

def get_struct_keys(r: DuckDBPyRelation):
    assert r.columns[1] == 'val'
    assert r.dtypes[1].id == 'struct'
    return [col[0] for col in r.dtypes[1].children]

def struct_pack(edges: list[str], r: DuckDBPyRelation):
    return 'struct_pack(' + ','.join(
        f'''"{edge_name}":="{edge_name}"'''
        for edge_name in edges
            if edge_name in r.columns
    ) + ')'

def get_index(typ: Type, r: DuckDBPyRelation):
    if len(typ.indexes) == 1:
        index = typ.indexes[0]
        if len(index) == 1:
            return r.select(f'''{index[0]} as _index, *''')
        else:
            return r.select(f'''list_value({','.join(index)}) as _index, *''')
    else:
        # flatten indexes
        index = [idx for idxs in typ.indexes for idx in idxs]
        return r.select(f'''{struct_pack(index, r)} as _index, *''')

class Staging:
    def __init__(self, typ: DefinedType, r: DuckDBPyRelation):
        assert typ.has_index
        self.tables = {}
        self.models = typ._models
        self.get_value(typ, r.select(f'list_value(ROW_NUMBER() OVER () - 1) as _, {struct_pack(typ.edges.keys(), r)} as val'))

    def get_value(self, typ: Type, r: DuckDBPyRelation):
        if typ.has_edges:
            edges = r.select('_')
            for edge_name, edge in typ.edges.items():
                if edge_name in get_struct_keys(r):
                    edge_rel = self.get_edge(edge, r.select(f'''list_append(_, '{edge_name}') as _, val.{edge_name} as val''')).set_alias(typ.ref + '.' + edge_name)
                    edge_rel = edge_rel.select(f'''array_pop_back(_) as _, val as {edge_name}''')
                    edges = edges.join(edge_rel, '_', how='left')
                else:
                    edges = edges.select(f'*, NULL as {edge_name}')
            
            if typ.has_index:
                edges = get_index(typ, edges)
                self.tables[typ.ref] = edges
                return edges.select(f'''_, _index as val''')
            else:
                return edges.select(f'''_, {struct_pack(typ.edges.keys(), edges)} as val''')
        
        return r
    
    def get_edge(self, edge: Edge, r: DuckDBPyRelation):
        if edge.multiple:
            r = r.select('''list_append(_, ROW_NUMBER() OVER () - 1) as _, unnest(val) as val''')

        r = self.get_value(edge.type, r)

        if edge.multiple:
            r = r.aggregate('array_pop_back(_) as _, list(val) as val','array_pop_back(_)')

        return r

    def __getitem__(self, ref: TYPE_REF):
        return self.tables[ref]
    
    def __setitem__(self, ref: TYPE_REF, r: DuckDBPyRelation):
        assert ref not in self.tables
        self.tables[ref] = r

    def __contains__(self, ref: TYPE_REF):
        return ref in self.tables