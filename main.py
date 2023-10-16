from pathlib import Path
from kyepy.parser import Parser
from kyepy.translate.to_json_schema import to_json_schema
DIR = Path(__file__).parent

if __name__ == '__main__':
    import sys
    file_path = DIR / 'examples/to_json_schema.kye'
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    p = Parser.from_file(file_path)
    p.print_tree()
    print(p.ast)
    json_schema = to_json_schema(p.ast)
    print(json_schema)