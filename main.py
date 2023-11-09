from pathlib import Path
from kyepy.parser.parser import Parser
from kyepy.parser.assign_scopes import assign_scopes, Scope
from kyepy.parser.assign_type_refs import assign_type_refs
from kyepy.parser.flatten_ast import flatten_ast
from pprint import pprint
from kyepy.compiled import CompiledDataset
from kyepy.dataset import Models
from kyepy.loader.loader import Loader
import duckdb
DIR = Path(__file__).parent

def compile(file_path):
    p = Parser.from_file(file_path)

    GLOBAL_SCOPE = Scope(name=None, parent=None)
    for global_type in ['Number','String','Boolean','Struct','Model']:
        GLOBAL_SCOPE[global_type] = '<built-in type>'

    assign_scopes(p.ast, scope=GLOBAL_SCOPE)
    assign_type_refs(p.ast)

    FORMAT = '{:<20} {:<20} {}'
    print(FORMAT.format('Scope', 'Type', 'Node'))
    print('-'*80)
    for path, node in p.ast.traverse():
        print(FORMAT.format(
            getattr(node.scope, 'path', '') or '',
            node.type_ref or '',
            '    '*(len(path)-1) + repr(node))
        )

    raw_models = flatten_ast(p.ast)
    pprint(raw_models)
    return raw_models


if __name__ == '__main__':
    import sys
    file_path = DIR / 'examples/yellow.kye'
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    
    raw_models = compile(file_path)
    models = CompiledDataset(models=raw_models)
    models = Models(models)

    loader = Loader(models)

    loader.from_json('Yellow', [{
        'id': 1,
        # 'size': 1,
        'meep': {
            "id": 1,
        },
        'parents': [{ 
            'id': 1,
            'admin': True,
            'name': 'Joe',
            'friends': [{
                'id': 3,
                'name': 'Bob',
            },{
                'id': 4,
                'name': 'Sally',
            }]
        },{
            'id': 2,
            'admin': False,
            'name': 'Mary',
            'friends': [{
                'id': 5,
                'name': 'Susan',
            },{
                'id': 4,
                'name': 'Sally',
            }]
        }],
        'tags': [1, 'hi', 'bye']
    },
    {
        'id': 2,
        # 'size': 2,
        'parents': [{ 
            'id': 3,
            'admin': True,
            'name': 'Bob',
            'friends': [{
                'id': 3,
                'name': 'Bob',
            },{
                'id': 4,
                'name': 'Sally',
            }]
        },{
            'id': 4,
            'admin': False,
            'name': 'Sarah',
            'friends': [{
                'id': 5,
                'name': 'Susan',
            },{
                'id': 4,
                'name': 'Sally',
            }]
        }],
    }
    ])

    loader.from_json('Yellow', [{
        'id': 1.0,
        # 'size': 2,
        'tags': ['hi', 'meep']
    }])

    for table_name, table in loader.tables.items():
        print(table_name)
        print(table)
    print('hi')