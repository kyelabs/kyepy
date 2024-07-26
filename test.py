import typing as t

import yaml
from pathlib import Path
import pandas as pd
from argparse import ArgumentParser

parser = ArgumentParser(description="Kye Test Runner")
parser.add_argument("--debug", action='store_true', help="Only run debug tests")
args = parser.parse_args()

from kye.kye import Kye
from kye.errors.validation_errors import ValidationErrorReporter

DIR = Path(__file__).resolve().parent
TEST_DIR =  DIR / 'tests'

ONLY_RUN_DEBUG = args.debug

def lookup(df, query: dict):
    mask = pd.Series(True, index=df.index)
    for prop, values in query.items():
        if type(values) is not list:
            values = [values]
        assert prop in df.columns
        mask &= df[prop].isin(values)
    return mask

if __name__ == "__main__":
    for file in TEST_DIR.glob('**/*.yaml'):
        print(str(file.relative_to(DIR)))
        test_cases = yaml.safe_load(file.open('r'))
        if test_cases is None:
            continue
        for test_case in test_cases:
            print(' ', test_case['feature'])
            for test in test_case['tests']:
                if ONLY_RUN_DEBUG and not test.get('debug'):
                    continue
                print('   ', test['test'])
                kye = Kye()
                success = kye.compile(test_case['schema'])
                if not success:
                    kye.reporter.report()
                    raise Exception('Failed to compile schema')
                for model_name, rows in test['data'].items():
                    kye.load_df(model_name, pd.DataFrame(rows))
                error_df = t.cast(ValidationErrorReporter, kye.reporter).error_df.copy()
                error_df['unused'] = True
                expected_errors = test.get('errors', [])
                if len(expected_errors) == 0 and kye.reporter.had_error:
                    kye.reporter.report()
                    raise Exception('Invalid when should have been valid')
                for err in expected_errors:
                    mask = lookup(error_df, err)
                    if not mask.any():
                        kye.reporter.report()
                        print(err)
                        print(error_df)
                        raise Exception('Expected error not found')
                    error_df.loc[mask, 'unused'] = False
                if error_df['unused'].any():
                    kye.reporter.report()
                    print(error_df[error_df['unused']].drop(columns=['unused']))
                    raise Exception('Found unexpected errors')
                if ONLY_RUN_DEBUG:
                    kye.reporter.report()