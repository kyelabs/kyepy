from kye.types import Type, Edge, TYPE_REF, EDGE, Models
from kye.loader.loader import Loader, struct_pack
from duckdb import DuckDBPyConnection, DuckDBPyRelation

class Validate:
    loader: Loader
    tables: dict[TYPE_REF, DuckDBPyRelation]

    def __init__(self, loader: Loader):
        self.loader = loader
        self.tables = {}

        self.db.sql('CREATE TABLE errors (rule_ref TEXT, error_type TEXT, object_id UINT64, val JSON);')
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
        err = err.select(f''' '{rule_ref}' as rule_ref, '{error_type}' as error_type, _index as object_id, to_json(val) as val''')
        err.insert_into('errors')
        return r.filter(f'''NOT ({condition})''')

    def check_for_index_collision(self, typ: Type, r: DuckDBPyRelation):
        packed_indexes = ','.join(f"list_pack({','.join(sorted(index))})" for index in typ.indexes)
        r = r.select(f'''_index, UNNEST([{packed_indexes}]) as index_val''')
        r = r.aggregate('index_val, list_distinct(list(_index)) as _indexes')

        r = r.select('index_val as val, unnest(_indexes) as _index, len(_indexes) > 1 as collision')

        self._add_errors_where(r,
            condition  = 'collision',
            rule_ref   = typ.ref, 
            error_type = 'NON_UNIQUE_INDEX'
        )
        # Select the good indexes
        return r.aggregate('_index, bool_or(collision) as collision').filter('not collision').select('_index')

    
    def _validate_model(self, typ: Type, r: DuckDBPyRelation):
        edges = r.aggregate('_index')

        # No need to check for conflicting indexes if there is only one
        if len(typ.indexes) > 1:
            edges = self.check_for_index_collision(typ, r)

        for edge_name, edge in typ.edges.items():
            edge_rel = r.select(f'''_index, {edge_name if edge_name in r.columns else 'CAST(NULL as VARCHAR)'} as val''')
            edge_rel = self._validate_edge(edge, edge_rel).set_alias(edge.ref)
            edge_rel = edge_rel.select(f'''_index, val as {edge_name}''')
            edges = edges.join(edge_rel, '_index', how='left')
        return edges

    def _validate_edge(self, edge: Edge, r: DuckDBPyRelation):
        agg_fun = 'list_distinct(flatten(list(val)))' if r.val.dtypes[0].id == 'list' else 'list_distinct(list(val))'
        r = r.aggregate(f'''_index, {agg_fun} as val''')

        if not edge.nullable:
            r = self._add_errors_where(r, 'len(val) == 0', edge.ref, 'NOT_NULLABLE')
        
        if not edge.multiple:
            r = self._add_errors_where(r, 'len(val) > 1', edge.ref, 'NOT_MULTIPLE')
            r = r.select(f'''_index, val[1] as val''')
        else:
            r = r.select(f'''_index, unnest(val) as val''')
        
        r = r.filter('val IS NOT NULL')
        r = self._validate_value(edge.returns, r)

        if edge.multiple:
            r = r.aggregate('_index, list(val) as val')
        
        return r
    
    def _validate_value(self, typ: Type, r: DuckDBPyRelation):
        # TODO: Look up object references and see if they exist

        if typ.kind == 'Boolean':
            r = self._add_errors_where(r, 'TRY_CAST(val as BOOLEAN) IS NULL', typ.ref, 'INVALID_VALUE')
        elif typ.kind == 'Number':
            r = self._add_errors_where(r, 'TRY_CAST(val AS DOUBLE) IS NULL', typ.ref, 'INVALID_VALUE')

        return r

    def __getitem__(self, model_name: TYPE_REF):
        return self.tables[model_name]
    
    def __repr__(self):
        return f"<Validate {','.join(self.tables.keys())}>"