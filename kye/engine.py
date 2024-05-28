from pathlib import Path
import pandas as pd

class Engine:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent / '../data'

    def has_table(self, table_name):
        return (self.base_dir / table_name).with_suffix('.csv').exists()
    
    def get_table(self, table_name):
        filename = (self.base_dir / table_name).with_suffix('.csv')
        return pd.read_csv(filename).infer_objects()