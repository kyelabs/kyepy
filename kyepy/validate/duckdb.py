from duckdb import DuckDBPyConnection, DuckDBPyRelation, ColumnExpression
from kyepy.kye_ast import *
from kyepy.dataset import Type, Edge, Dataset, TYPE_REF

def struct_pack(typ: Type, r: DuckDBPyRelation):
    struct_edges = {}
    for edge_name in typ.edges.keys():
        if edge_name not in r.columns:
            struct_edges[edge_name] = 'NULL'
        else:
            struct_edges[edge_name] = f'"{edge_name}"'
    return 'struct_pack(' + ','.join(f'''"{name}":={val}''' for name, val in struct_edges.items()) + ')'

def get_value(typ: Type, r: DuckDBPyRelation):
    if typ.issubclass('Struct'):
        edges = r.select('_')
        for edge_name, edge in typ.edges.items():
            edge_rel = get_edge(edge, r.select(f'''list_append(_, '{edge_name}') as _, val.{edge_name} as val''')).set_alias(r.alias + '.' + edge_name)
            edge_rel = edge_rel.select(f'''array_pop_back(_) as _, val as {edge_name}''')
            edges = edges.join(edge_rel, '_', how='left')
        return edges.select(f'''_, {struct_pack(typ, edges)} as val''')
    
    return r

def get_edge(typ: Edge, r: DuckDBPyRelation):
    if typ.multiple:
        r = r.select('''list_append(_, ROW_NUMBER() OVER () - 1) as _, unnest(val) as val''')

    r = get_value(typ._type, r)

    if typ.multiple:
        r = r.aggregate('array_pop_back(_) as _, list(val) as val','array_pop_back(_)')

    return r

def get_duckdb(typ: Type, r: DuckDBPyRelation):
    assert typ.issubclass('Model')
    
    r = get_value(typ, r.select(f'list_value(ROW_NUMBER() OVER () - 1) as _, {struct_pack(typ, r)} as val'))
    return r.select('val.*')