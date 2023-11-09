import duckdb
from duckdb import DuckDBPyRelation
from kyepy.dataset import Models
from kyepy.loader.json_lines import from_json
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
    # Hash the index columns
    r = r.select(f'''hash({struct_pack(sorted(typ.index), r)}) as _index, *''')

    # Filter out null indexes
    r = r.filter(f'''{' AND '.join(edge  + ' IS NOT NULL' for edge in typ.index)}''')
    return r

class Loader:
    """
    The loader is responsible for normalizing the shape of the data. It makes sure that
    all of the columns are present (filling in nulls where necessary) and also computes
    the index hash for each row so that it is easy to join the data together later.
    
    The loader operates for each chunk of the data while it is loading. So it does not
    do any cross table aggregations or validation.

    Any value normalization needs to be done here so that the index hash is consistent.
    """
    tables: dict[TYPE_REF, duckdb.DuckDBPyRelation]

    def __init__(self, models: Models):
        self.tables = {}
        self.models = models
        self.db = duckdb.connect(':memory:')
        self.chunks = {}

    def _insert(self, model_name: TYPE_REF, r: duckdb.DuckDBPyRelation):
        table_name = f'"{model_name}.staging"'
        if model_name not in self.tables:
            r.create(table_name)
            self.tables[model_name] = self.db.table(table_name)
        else:
            r.insert_into(table_name)

    def _load(self, typ: DefinedType, r: duckdb.DuckDBPyRelation):
        chunk_id = typ.name + '_' + str(len(self.chunks) + 1)
        chunk = r.select(f'''list_value('{chunk_id}', ROW_NUMBER() OVER () - 1) as _, {struct_pack(typ.edges.keys(), r)} as val''').set_alias(chunk_id)
        self.chunks[chunk_id] = chunk
        self._get_value(typ, chunk)

    def _get_value(self, typ: Type, r: DuckDBPyRelation):
        if typ.has_edges:
            edges = r.select('_')
            for edge_name, edge in typ.edges.items():
                if edge_name in get_struct_keys(r):
                    edge_rel = self._get_edge(edge, r.select(f'''list_append(_, '{edge_name}') as _, val.{edge_name} as val''')).set_alias(typ.ref + '.' + edge_name)
                    edge_rel = edge_rel.select(f'''array_pop_back(_) as _, val as {edge_name}''')
                    edges = edges.join(edge_rel, '_', how='left')
                else:
                    edges = edges.select(f'*, CAST(NULL as VARCHAR) as {edge_name}')
            
            if typ.has_index:
                edges = get_index(typ, edges)
                self._insert(typ.ref, edges)
                return edges.select(f'''_, _index as val''')
            else:
                return edges.select(f'''_, {struct_pack(typ.edges.keys(), edges)} as val''')
        
        elif r.dtypes[1].id != 'varchar':
            dtype = r.dtypes[1].id
            r = r.select(f'''_, CAST(val AS VARCHAR) as val''')
            # remove trailing '.0' from decimals so that
            # they will match integers of the same value
            if dtype in ['double','decimal','real']:
                r = r.select(f'''_, REGEXP_REPLACE(val, '\\.0$', '') as val''')
        # else:
        #     dtype = r.dtypes[1].id
        #     base_type = typ.base.name
        #     converted = True
        #     if base_type == 'Boolean' and dtype != 'boolean':
        #         r = r.select(f'''_, TRY_CAST(val AS BOOLEAN) as val, val as raw''')
        #     elif base_type == 'Number' and dtype == 'varchar':
        #         r = r.select(f'''_, TRY_CAST(val AS DOUBLE) as val, val as raw''')
        #     elif base_type == 'String' and dtype != 'varchar':
        #         r = r.select(f'''_, CAST(val AS VARCHAR) as val, val as raw''')
        #     else:
        #         converted = False

        #     if converted:
        #         errors = r.filter('val IS NULL AND raw IS NOT NULL')
        #         if errors.shape[0] > 0:
        #             path, bad, raw = errors.fetchone()
        #             raise ValueError(f'''Invalid value for {repr(typ)}: ({'.'.join(path)}) "{raw}"''')
        return r
    
    def _get_edge(self, edge: Edge, r: DuckDBPyRelation):
        if edge.multiple:
            r = r.select('''_, unnest(val) as val''').select('list_append(_, ROW_NUMBER() OVER (PARTITION BY _) - 1) as _, val')

        r = self._get_value(edge.type, r)

        if edge.multiple:
            r = r.aggregate('array_pop_back(_) as _, list(val) as val','array_pop_back(_)')

        return r
    
    def from_json(self, model_name: TYPE_REF, data: list[dict]):
        r = from_json(self.models[model_name], data, self.db)
        self._load(self.models[model_name], r)

    def __getitem__(self, model_name: str):
        return self.tables[model_name]

    def __repr__(self):
        return f"<Loader {','.join(self.tables.keys())}>"