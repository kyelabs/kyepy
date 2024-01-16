from functools import wraps
import inspect
from pathlib import Path
import yaml
from kye.types import from_compiled
from kye.engine.engine import DuckDBEngine

__all__ = [
    'validate',
]

_global_engine = None

def find_kye_file(filepath: str):
    dir = Path(filepath).parent
    models_file = dir / 'models.yaml'
    if not models_file.exists():
        raise Exception(f'Could not find models.yaml file in directory "{dir}"')
    return models_file

def get_engine(filepath: str):
    global _global_engine
    if _global_engine is None:
        with find_kye_file(filepath).open('r') as f:
            src = yaml.safe_load(f)
        models = from_compiled(src)
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