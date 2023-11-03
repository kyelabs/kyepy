from pathlib import Path
from kyepy.parser import Parser
from kyepy.loader.json_lines import JsonLineLoader
from kyepy.assign_scopes import assign_scopes, Scope
from kyepy.assign_type_refs import assign_type_refs
from kyepy.flatten_ast import flatten_ast
from pprint import pprint
from kyepy.dataset import Dataset, GLOBALS
from kyepy.validate.duckdb import get_duckdb
import duckdb
DIR = Path(__file__).parent

if __name__ == '__main__':
    import sys
    file_path = DIR / 'examples/yellow.kye'
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    p = Parser.from_file(file_path)

    GLOBAL_SCOPE = Scope(name=None, parent=None)
    for global_type in GLOBALS.keys():
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
    models = Dataset(models=raw_models)

    MODEL = models['Yellow']
    DATA = [{
        'id': 1,
        # 'size': 1,
        'meep': {
            "id": 1,
        },
        'user': { 
            'id': 1,
            '_': 'hi',
            'name': 'ben',
        },
    }, {
        'id': 1,
    }]
    with JsonLineLoader(models, DIR / 'data') as loader:
        loader.write('Yellow', DATA)
    con = duckdb.connect(':memory:')
    loader.load_duckdb(con)

    r = get_duckdb(MODEL, con.table('Yellow'))
    print(r)
    print('hi')