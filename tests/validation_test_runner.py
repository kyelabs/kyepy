import typing as t
import sys
from pathlib import Path
from argparse import ArgumentParser


import yaml
import pandas as pd

parser = ArgumentParser(description="Kye Test Runner")
parser.add_argument("--debug", action='store_true', help="Only run debug tests")
args = parser.parse_args()

from kye.kye import Kye
from kye.errors.validation_errors import ValidationErrorReporter

PROJECT_DIR = Path(__file__).resolve().parent / '..'
TESTS_FILEPATH = PROJECT_DIR / 'tests/validation_tests.yaml'

ONLY_RUN_DEBUG = args.debug

class Printer:    
    def __init__(self):
        self.feature = None
    
    def update_loc(self, feature):
        if self.feature != feature:
            print(' ', feature)
            self.feature = feature
    
    def success(self, feature, test):
        self.update_loc(feature)
        print('   ✅ ' + test)
    
    def failure(self, feature, test):
        self.update_loc(feature)
        print('   ❌ ' + test)
        

def lookup(df, query: dict):
    mask = pd.Series(True, index=df.index)
    for prop, values in query.items():
        if type(values) is not list:
            values = [values]
        assert prop in df.columns
        mask &= df[prop].isin(values)
    return mask

if __name__ == "__main__":
    printer = Printer()
    print('Running tests in ' + str(TESTS_FILEPATH.relative_to(PROJECT_DIR)))
    test_cases = yaml.safe_load(TESTS_FILEPATH.open('r'))
    if test_cases is None:
        test_cases = []

    for test_case in test_cases:
        compiled = None
        
        for test in test_case['tests']:
            if ONLY_RUN_DEBUG and not test.get('debug'):
                continue
            if not ONLY_RUN_DEBUG and test.get('debug'):
                print('WARNING: debug test found in non-debug mode')
            
            if compiled is None:
                kye = Kye()
                successful_compilation = kye.compile(test_case['schema'])
                
                # Check for successful compilation
                if not successful_compilation:
                    printer.update_loc(test_case['feature'])
                    print('\n'+test_case['schema'])
                    kye.reporter.report()
                    raise Exception('Failed to compile schema')
                compiled = kye.compiled
                assert compiled is not None
            
            kye.load_compiled(compiled)
            
            # Load the data
            for model_name, rows in test['data'].items():
                kye.load_df(model_name, pd.DataFrame(rows))
            
            error_df = t.cast(ValidationErrorReporter, kye.reporter).error_df.copy()
            error_df['unused'] = True
            expected_errors = test.get('errors', [])
            
            # Check if we expected any errors
            if len(expected_errors) == 0 and kye.reporter.had_error:
                printer.failure(test_case['feature'], test['test'])
                kye.reporter.report()
                print(error_df[error_df['unused']].drop(columns=['unused']))
                raise Exception('Invalid when should have been valid')

            # Check if each error is present
            for err in expected_errors:
                mask = lookup(error_df, err)
                if not mask.any():
                    printer.failure(test_case['feature'], test['test'])
                    kye.reporter.report()
                    print(err)
                    print(error_df)
                    raise Exception('Expected error not found')
                error_df.loc[mask, 'unused'] = False

            # Check if there are any unexpected errors
            if error_df['unused'].any():
                printer.failure(test_case['feature'], test['test'])
                kye.reporter.report()
                print(error_df[error_df['unused']].drop(columns=['unused']))
                raise Exception('Unused errors')

            # Success!
            printer.success(test_case['feature'], test['test'])

            # If debugging then print the errors
            if ONLY_RUN_DEBUG:
                kye.reporter.report()
    if printer.feature is None:
        print('No tests found')