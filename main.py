from pathlib import Path
from kye.types import from_compiled
from kye.engine.engine import DuckDBEngine
import yaml
DIR = Path(__file__).parent

if __name__ == '__main__':
    with open(DIR / 'examples/compiled.yaml') as f:
        src = yaml.safe_load(f)
    
    models = from_compiled(src)
    engine = DuckDBEngine(models)
    engine.load_json('User',[{
        'id': 0,
        'name': None,
    }, {
        'id': 0,
        'name': 'Box'
    }, {
        'id': 1,
        'name': ['Bob','Macro'],
    }, {
        'id': 2,
        'name': 'Bill',
    }, {
        'age': 23,
    }, {
        'id': 3,
    }, {
        'id': 4,
        'name': 'Bill',
    }])
    engine.load_json('Post', [{
        'id': 0,
        'authors': 'Bob',
        'published_date': '2020-01-01',
    }, {
        'id': 0,
        'authors': 'Bill',
        'published_date': '2020-04-01'
    }, {
        'id': 1,
        'authors': ['Bob', 'Bill'],
    }, {
        'id': 2,
        'authors': None
    }, {
        'id': 3,
    }])
    engine.validate()
    
    print(engine.get_table('User'))
    print(engine.get_table('Post'))
    print(engine.errors)