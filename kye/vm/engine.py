from pathlib import Path
from collections import defaultdict
import pandas as pd

class Engine:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent / '../../data'
        self.files = defaultdict(list)
        for p in self.base_dir.glob('*'):
            if p.suffix in {'.csv','.json','.jsonl'}:
                self.files[p.stem.lower()].append(p.resolve())

    def has_table(self, table_name: str):
        return table_name.lower() in self.files
    
    def get_table(self, table_name: str) -> pd.DataFrame:
        files = self.files[table_name.lower()]
        if len(files) == 0:
            raise FileNotFoundError(f"Table {table_name} not found.")
        if len(files) > 1:
            raise FileNotFoundError(f"Multiple files found for table {table_name}.")
        file = files[0]
        if file.suffix == '.csv':
            return pd.read_csv(file)
        elif file.suffix == '.json':
            return pd.read_json(file)
        elif file.suffix == '.jsonl':
            return pd.read_json(file, lines=True)
        else:
            raise ValueError(f"Unknown file type {file.suffix}")