import duckdb
from duckdb import DuckDBPyRelation, DuckDBPyConnection
from kye.loader.json_lines import from_json
from kye.types import Type, EDGE, TYPE_REF


def append_table(con: DuckDBPyConnection, orig: DuckDBPyRelation, new: DuckDBPyRelation):
    """
    This function will not be needed in the future if we can figure out a standard way
    to create the staging tables with the correct types before any data is uploaded.
    """

    def get_dtypes(r: DuckDBPyRelation):
        return dict(zip(r.columns, r.dtypes))

    orig_dtypes = get_dtypes(orig)
    new_dtypes = get_dtypes(new)

    # Check that the types of the columns match
    for col in set(orig_dtypes) & set(new_dtypes):
        if orig_dtypes[col] != new_dtypes[col]:
            raise ValueError(f'''Column {col} has conflicting types: {orig_dtypes[col]} != {new_dtypes[col]}''')

    # Alter the original table to include any new columns
    for col in set(new_dtypes) - set(orig_dtypes):
        con.sql(f'''ALTER TABLE "{orig.alias}" ADD COLUMN {col} {new_dtypes[col]}''')

    # preserve the order of columns from the original table
    # and cast any new columns to null
    new = new.select(', '.join(
        col if col in new_dtypes
            else f'CAST(NULL as {orig_dtypes[col]}) as {col}'
        for col in con.table(f'"{orig.alias}"').columns
    ))
    
    new.insert_into(f'"{orig.alias}"')

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
    # If I store types and edges in separate relations, then that will allow me
    # to have a more standard storage format and not have to append columns to tables
    # right? Because every edge table would look like (index:int64, value:str, args:list[str])
    # It would also allow me to do my quad store if I really wanted to.
    tables: dict[TYPE_REF, duckdb.DuckDBPyRelation]
    models: dict[TYPE_REF, Type]
    db: duckdb.DuckDBPyConnection
    chunks: dict[str, duckdb.DuckDBPyRelation]

    def __init__(self, models: dict[TYPE_REF, Type]):
        self.tables = {}
        self.models = models
        self.db = duckdb.connect(':memory:')
        self.chunks = {}

    def _insert(self, model_name: TYPE_REF, r: duckdb.DuckDBPyRelation):
        table_name = f'"{model_name}.staging"'
        if model_name not in self.tables:
            r.create(table_name)
        else:
            append_table(self.db, self.tables[model_name], r)
        self.tables[model_name] = self.db.table(table_name)

    def _load(self, typ: Type, r: duckdb.DuckDBPyRelation):
        chunk_id = typ.ref + '_' + str(len(self.chunks) + 1)
        chunk = r.select(f'''list_value('{chunk_id}', ROW_NUMBER() OVER () - 1) as _, {struct_pack(typ.edges, r)} as val''').set_alias(chunk_id)
        self.chunks[chunk_id] = chunk
        self._get_value(typ, chunk)

    def _get_value(self, typ: Type, r: DuckDBPyRelation):
        if typ.has_index:
            edges = r.select('_')
            for edge in typ.edges:
                if edge in get_struct_keys(r):
                    edge_rel = self._get_edge(typ, edge, r.select(f'''list_append(_, '{edge}') as _, val.{edge} as val''')).set_alias(typ.ref + '.' + edge)
                    edge_rel = edge_rel.select(f'''array_pop_back(_) as _, val as {edge}''')
                    edges = edges.join(edge_rel, '_', how='left')
            
            edges = get_index(typ, edges)
            self._insert(typ.ref, edges)
            return edges.select(f'''_, _index as val''')
        
        # Eventually this will be replaced with a custom function for normalizing
        # values right? Like a DateTime type needs to be converted into a standard
        # format for index and equivalency checks right?
        # The standard format that it is converted into might also depend on the
        # storage system
        elif r.dtypes[1].id != 'varchar':
            dtype = r.dtypes[1].id
            r = r.select(f'''_, CAST(val AS VARCHAR) as val''')
            # remove trailing '.0' from decimals so that
            # they will match integers of the same value
            if dtype in ['double','decimal','real']:
                r = r.select(f'''_, REGEXP_REPLACE(val, '\\.0$', '') as val''')
        return r
    
    def _get_edge(self, typ: Type, edge: EDGE, r: DuckDBPyRelation):
        if typ.allows_multiple(edge):
            r = r.select('''_, unnest(val) as val''').select('list_append(_, ROW_NUMBER() OVER (PARTITION BY _) - 1) as _, val')

        r = self._get_value(typ.get_edge(edge), r)

        if typ.allows_multiple(edge):
            r = r.aggregate('array_pop_back(_) as _, list(val) as val','array_pop_back(_)')

        return r
    
    def from_json(self, model_name: TYPE_REF, data: list[dict]):
        r = from_json(self.models[model_name], data, self.db)
        self._load(self.models[model_name], r)

    def __getitem__(self, model_name: str):
        return self.tables[model_name]

    def __repr__(self):
        return f"<Loader {','.join(self.tables.keys())}>"