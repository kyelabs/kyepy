from kye.compiler.models import Type, EDGE
from duckdb import DuckDBPyConnection, DuckDBPyRelation

def struct_pack(edges: list[str], r: DuckDBPyRelation):
    return 'struct_pack(' + ','.join(
        f'''"{edge_name}":="{edge_name}"'''
        for edge_name in edges
            if edge_name in r.columns
    ) + ')'

def format_value(val):
    if isinstance(val, float):
        val = str(val)
        return val[:-2] if val.endswith('.0') else val
    if isinstance(val, int):
        return str(val)
    if isinstance(val, bool):
        return 'true' if val else 'false'
    if isinstance(val, str):
        return "'" + val.replace('\\', '\\\\').replace("'","\\'") + "'"
    raise ValueError('Unknown value type')

def value_list(strings: list[str]):
    return ','.join(format_value(string) for string in strings)

def flag(err_msg: str, condition: str, r: DuckDBPyRelation, **kwargs):
    fields = ["'" + err_msg + "'"]
    for field in ['tbl','idx','row','col','val']:
        if field in kwargs:
            if kwargs[field] is None:
                fields.append('NULL')
            else:
                fields.append("'" + kwargs[field] + "'")
        elif field in r.columns:
            fields.append(field)
        else:
            fields.append('NULL')
    
    err = r.filter(condition).select(','.join(fields))
    err.insert_into('errors')
    return r.filter(f'''NOT({condition})''')

def collect(groupby, relations: dict[str, DuckDBPyRelation]):
    collected = None
    for alias, r in relations.items():
        assert len(r.columns) == 2
        assert r.columns[0] == groupby
        r = r.select(f'''{groupby}, {r.columns[1]} as {alias}''').set_alias(alias)
        collected = collected.join(r, groupby, how='outer') if collected else r
    return collected

def row_index(r: DuckDBPyRelation, index: list[str], name: str = 'idx'):
    r = r.filter(' AND '.join(f'{idx} IS NOT NULL' for idx in index))\
        .select(f'''row, hash({struct_pack(sorted(index), r)}) as {name}''')
    return r

def row_indexes(edges: DuckDBPyRelation, typ: Type):
    global_index = row_index(edges, typ.index).set_alias('idx')
    partial_index = None
    for idx in typ.indexes:
        r = row_index(edges, idx, name='partial')
        partial_index = partial_index.union(r) if partial_index else r
    r = partial_index.join(global_index, 'row', how='left')
    # Create a map of partial ids to full ids
    partial_map = r.aggregate('partial, unnest(list_distinct(list(idx))) as idx').set_alias('partial_map')
    # Redefine index using the partial_map
    r = r.select('row, partial').join(partial_map, 'partial', how='left')
    return r

def compute_index(typ: Type, table: DuckDBPyRelation):
    edges = table.filter(f'''col in ({value_list(typ.index)})''')
    edges = flag('CONFLICTING_INDEX', 'cnt > 1',
        edges.aggregate('''row, col, first(val) as val, count(distinct(val)) as cnt'''), tbl=typ.ref, val=None)
    edges = collect('row', {
        col: edges.filter(f"col = '{col}'").select('row, val')
        for col in typ.index
    })
    indexes = row_indexes(edges, typ)
    r = table.aggregate('row').join(indexes, 'row', how='left')
    r = flag('MISSING_INDEX', 'partial IS NULL', r, tbl=typ.ref)
    r = flag('INCOMPLETE_INDEX', 'idx IS NULL', r, tbl=typ.ref)
    r = flag('CONFLICTING_INDEX', 'cnt > 1',
        r.aggregate('row, first(idx) as idx, count(distinct(idx)) as cnt'), tbl=typ.ref, idx=None)
    r = r.select('row, idx')
    return r


def check_edge(typ: Type, edge: EDGE, table: DuckDBPyRelation):
    column = table.filter(f"col = '{edge}'")
    if not typ.allows_multiple(edge):
        column = flag('CONFLICTING_EDGE', 'cnt > 1',
            column.aggregate('tbl, idx, col, unnest(list(distinct(val))) as val, count(distinct(val)) as cnt'), val=None)
    if not typ.allows_null(edge):
        flag('MISSING_EDGE', 'true',
             table.aggregate('tbl,idx').join(column.select('tbl,idx').set_alias('col'), 'tbl,idx', how='anti'))
    check_value(typ.get_edge(edge), column)

def check_value(typ: Type, col: DuckDBPyRelation):
    for assertion in typ.assertions:
        if assertion.op == 'type':
            if assertion.arg == 'number':
                col = flag('INVALID_VALUE', 'TRY_CAST(val as DOUBLE) IS NULL', col)
            elif assertion.arg == 'boolean':
                col = flag('INVALID_VALUE', 'TRY_CAST(val as BOOLEAN) IS NULL', col)
        elif assertion.op == 'eq':
            col = flag('INVALID_VALUE', f'val NOT IN ({value_list(assertion.arg)})', col)
        elif assertion.op == 'ne':
            col = flag('INVALID_VALUE', f'val IN ({value_list(assertion.arg)})', col)
        elif assertion.op == 'gt':
            col = flag('INVALID_VALUE', f'val <= {format_value(assertion.arg)}', col)
        elif assertion.op == 'gte':
            col = flag('INVALID_VALUE', f'val < {format_value(assertion.arg)}', col)
        elif assertion.op == 'lt':
            col = flag('INVALID_VALUE', f'val >= {format_value(assertion.arg)}', col)
        elif assertion.op == 'lte':
            col = flag('INVALID_VALUE', f'val > {format_value(assertion.arg)}', col)

def check_table(typ: Type, db: DuckDBPyConnection):
    table = db.table('edges').filter(f'''tbl = '{typ.ref}' ''')
    index = compute_index(typ, table)
    db.sql(f'''
    UPDATE edges
        SET idx=index.idx
        FROM index
        WHERE edges.row = index.row
          AND edges.tbl = '{typ.ref}';
    ''')
    table = table.filter('idx IS NOT NULL')
    for edge in typ.edges:
        check_edge(typ, edge, table)