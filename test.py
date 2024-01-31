from kye.compiler.models import Models
from kye.engine.pandas_engine import PandasEngine
import yaml
from pathlib import Path
import pandas as pd

DIR = Path(__file__).resolve().parent
TEST_DIR =  DIR / 'tests'

if __name__ == "__main__":
    for file in TEST_DIR.glob('**/*.yaml'):
        print(str(file.relative_to(DIR)))
        test_cases = yaml.safe_load(file.open('r'))
        for test_case in test_cases:
            print(' ', test_case['description'])
            models = Models.from_script(test_case['schema'])
            engine = PandasEngine(models)
            for test in test_case['tests']:
                print('   ', test['description'])
                for model, rows in test['data'].items():
                    df = pd.DataFrame(rows)
                    errors = engine.validate(model, df)
                    if len(errors) > 0 and test['valid']:
                        for error in errors:
                            print('     ', error)
                        raise Exception('Invalid when should have been valid')
                    if len(errors) == 0 and not test['valid']:
                        raise Exception('Valid when should have been invalid')
