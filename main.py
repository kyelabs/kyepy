from pathlib import Path
import kye
from kye.loader.loader import Loader
from kye.validate import Validate
from kye.types import from_compiled
import yaml
DIR = Path(__file__).parent

if __name__ == '__main__':
    with open(DIR / 'examples/compiled.yaml') as f:
        src = yaml.safe_load(f)
    
    models = from_compiled(src)
    loader = Loader(models)
    loader.from_json('User', [{
        'id': 1,
        'name': 'Joe',
    }, {
        'id': 2,
        'name': 'Bill',
    }])
    loader.from_json('User', [{
        'id': 1,
        'name': 'Joey', # conflicting name
    }])
    validate = Validate(loader)
    errors = validate.errors.aggregate(f"rule_ref, error_type").df()
    if not errors.empty:
        print('\nThe following validation errors were found:')
        print(errors)
    else:
        print('\n\tNo validation errors found.\n')
    print('hi')