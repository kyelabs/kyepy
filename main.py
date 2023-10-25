from pathlib import Path
from kyepy.parser import Parser
from kyepy.validate.python_row import validate_python
from kyepy.loader.json_lines import JsonLineLoader
from kyepy.transform.python_to_json import flatten_python_row
from kyepy.assign_scopes import assign_scopes, Scope
from kyepy.assign_type_refs import assign_type_refs
from kyepy.flatten_ast import flatten_ast
from pprint import pprint
from kyepy.dataset import Dataset
import duckdb
DIR = Path(__file__).parent

if __name__ == '__main__':
    import sys
    file_path = DIR / 'examples/yellow.kye'
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    p = Parser.from_file(file_path)

    GLOBAL_SCOPE = Scope(name=None, parent=None)
    GLOBAL_SCOPE['Number'] = '<built-in type>'
    GLOBAL_SCOPE['String'] = '<built-in type>'

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
    print('hi')

    # MODEL = p.ast.get_local_definition('Yellow')
    # DATA = [{
    #     'id': 1,
    #     'hi': None,
    #     'meep': [{
    #         'id': 2,
    #     }],
    #     'user_id': { 'id': 2, 'missing': 'hi', 'name': 'ben' },
    # }]
    # with JsonLineLoader(DIR / 'data') as loader:
    #     for row in DATA:
    #         try:
    #             validate_python(MODEL, row)
    #         except Exception as e:
    #             print(e)
    #             continue
    #         flatten_python_row(MODEL, row, loader)
    # con = duckdb.connect(':memory:')
    # loader.load_duckdb(con)

    # json_schema = to_json_schema(p.ast)
    # print(json_schema)