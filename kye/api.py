from functools import wraps
import inspect
from pathlib import Path
import yaml
from kye.engine.engine import DuckDBEngine
from kye.compiler.models import Models

__all__ = [
    'validate',
]

_global_engine = None

def load_yaml_models(filepath: Path):
    with filepath.open('r') as f:
        src = yaml.safe_load(f)
        return Models.from_compiled(src)

def load_kye_models(filepath: Path):
    with filepath.open('r') as f:
        src = f.read()
        return Models.from_script(src)

def load_models(filepath: str):
    dir = Path(filepath).parent
    yaml_file = dir / 'models.yaml'
    kye_file = dir / 'models.kye'
    if yaml_file.exists() and kye_file.exists():
        raise Exception('Please only define the models.yaml file or the models.kye file, not both')
    elif yaml_file.exists():
        return load_yaml_models(yaml_file)
    elif kye_file.exists():
        return load_kye_models(kye_file)
    else:
        raise Exception(f'Please define either a models.yaml file or models.kye file in "{dir}"')

def get_engine(filepath: str):
    global _global_engine
    if _global_engine is None:
        models = load_models(filepath)
        _global_engine = DuckDBEngine(models)
    return _global_engine

def validate(model: str):
    def wrapper(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            engine = get_engine(inspect.getfile(fn))
            assert model in engine.models, f'Undefined model {model}'
            data = fn(*args, **kwargs)
            engine.load_json(model, data)
            engine.validate()
            errors = engine.get_errors()
            if len(errors) > 1:
                messages = '\n\t'.join(
                    err.message
                    for err in errors
                )
                raise Exception(f'Validation Errors:\n\t{messages}')
            elif len(errors) == 1:
                raise Exception(errors[0].message)
            return data
        return wrapped
    return wrapper