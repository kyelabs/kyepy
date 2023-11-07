import duckdb
from kyepy.dataset import Models
from kyepy.loader.json_lines import from_json
from kyepy.loader.format import Format
from kyepy.dataset import TYPE_REF

class Loader:
    def __init__(self, models: Models):
        self.tables = {}
        self.models = models
        self.db = duckdb.connect(':memory:')
    
    def _load(self, model_name: TYPE_REF, r: duckdb.DuckDBPyRelation):
        formatted = Format(self.models[model_name], r)
        for name, table in formatted.tables.items():
            self._insert(name, table)

    def _insert(self, model_name: TYPE_REF, r: duckdb.DuckDBPyRelation):
        table_name = f'"{model_name}.staging"'
        if model_name not in self.tables:
            r.create(table_name)
            self.tables[model_name] = self.db.table(table_name)
        else:
            r.insert_into(table_name)

    def __getitem__(self, model_name: str):
        return self.tables[model_name]
    
    def from_json(self, model_name: TYPE_REF, data: list[dict]):
        r = from_json(self.models[model_name], data, self.db)
        self._load(model_name, r)

    def __repr__(self):
        return f"<Loader {','.join(self.tables.keys())}>"