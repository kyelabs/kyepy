from pathlib import Path
import kye
DIR = Path(__file__).parent

if __name__ == '__main__':
    with open(DIR / 'examples/yellow.kye') as f:
        text = f.read()
    
    models = kye.compile(text)