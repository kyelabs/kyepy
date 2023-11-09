from kyepy.dataset import Models, Type, Edge, TYPE_REF
from kyepy.loader.loader import Loader
from duckdb import DuckDBPyConnection, DuckDBPyRelation

class Validate:
    loader: Loader
    tables: dict[TYPE_REF, DuckDBPyRelation]

    def __init__(self, loader: Loader):
        self.loader = loader
        self.tables = {}

        self.db.sql('CREATE TABLE errors (rule_ref TEXT, error_type TEXT, object_id UINT64, locations TEXT[][], val JSON);')
        self.errors = self.db.table('errors')

        for model_name, table in self.loader.tables.items():
            table = self._validate_model(self.models[model_name], table)
            table_name = f'"{model_name}.validated"'
            table.create(table_name)
            self.tables[model_name] = self.db.table(table_name)
    
    @property
    def db(self) -> DuckDBPyConnection:
        return self.loader.db
    
    @property
    def models(self) -> Models:
        return self.loader.models

    def _add_errors_where(self, r: DuckDBPyRelation, condition: str, rule_ref: str, error_type: str):
        err = r.filter(condition)
        err = err.select(f''' '{rule_ref}' as rule_ref, '{error_type}' as error_type, _index as object_id, _ as locations, val''')
        err.insert_into('errors')
        return r.filter(f'''NOT ({condition})''')
    
    def _validate_model(self, typ: Type, r: DuckDBPyRelation):
        edges = r.aggregate('_index')
        for edge_name, edge in typ.edges.items():
            edge_rel = self._validate_edge(edge, r.select(f'''_index, list_append(_, '{edge_name}') as _, {edge_name} as val''')).set_alias(edge.ref)
            edge_rel = edge_rel.select(f'''_index, val as {edge_name}''')
            edges = edges.join(edge_rel, '_index', how='left')
        return edges

    def _validate_edge(self, edge: Edge, r: DuckDBPyRelation):
        agg_fun = 'list_distinct(flatten(list(val)))' if r.val.dtypes[0].id == 'list' else 'list_distinct(list(val))'
        r = r.aggregate(f'''_index, list(_) as _, count(distinct(val)) as _count, {agg_fun} as val''')

        if not edge.nullable:
            r = self._add_errors_where(r, '_count == 0', edge.ref, 'NOT_NULLABLE')
        
        if not edge.multiple:
            r = self._add_errors_where(r, '_count > 1', edge.ref, 'NOT_MULTIPLE')
            r = r.select(f'''_index, _, val[1] as val''')
        
        return r.select('_index, _, val')

    def __getitem__(self, model_name: TYPE_REF):
        return self.tables[model_name]
    
    def __repr__(self):
        return f"<Validate {','.join(self.tables.keys())}>"