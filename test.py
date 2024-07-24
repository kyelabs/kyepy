from kye.kye import Kye
import yaml
from pathlib import Path
import pandas as pd

DIR = Path(__file__).resolve().parent
TEST_DIR =  DIR / 'tests'

if __name__ == "__main__":
    for file in TEST_DIR.glob('**/*.yaml'):
        print(str(file.relative_to(DIR)))
        test_cases = yaml.safe_load(file.open('r'))
        if test_cases is None:
            continue
        for test_case in test_cases:
            print(' ', test_case['feature'])
            for test in test_case['tests']:
                print('   ', test['test'])
                kye = Kye()
                success = kye.compile(test_case['schema'])
                if not success:
                    kye.reporter.report()
                    raise Exception('Failed to compile schema')
                for model_name, rows in test['data'].items():
                    kye.load_df(model_name, pd.DataFrame(rows))
                errors = kye.reporter.errors
                if test.get('debug'):
                    breakpoint()
                if len(errors) > 0 and test['valid']:
                    for error in errors:
                        print('     ', error)
                    raise Exception('Invalid when should have been valid')
                if len(errors) == 0 and not test['valid']:
                    raise Exception('Valid when should have been invalid')
