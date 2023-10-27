import json
from pathlib import Path
import duckdb

class JsonLineLoader:
    
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        assert self.directory.is_dir()
        self.files = {}
        self._is_closed = False
    
    def _get_file_path(self, model_name):
        return self.directory / f'{model_name}.json'

    def _get_file_handler(self, model_name):
        if model_name not in self.files:
            self.files[model_name] = self._get_file_path(model_name).open('w', encoding='utf-8')
        return self.files[model_name]

    def write(self, model, data):
        assert not self._is_closed, 'Cannot write to a closed loader'
        f = self._get_file_handler(model.get_model_name())
        json.dump(data, f)
        f.write('\n')

    def close(self):
        self._is_closed = True
        for file in self.files.values():
            file.close()
    
    def load_duckdb(self, con):
        assert self._is_closed, 'Cannot load to duckdb until the loader is closed'
        assert len(self.files) > 0, 'Cannot load to duckdb until at least one model has been written'
        for model_name, file in self.files.items():
            con.read_json(file.name).to_table('"' + model_name + '"')
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()