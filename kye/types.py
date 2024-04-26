from __future__ import annotations
import typing as t
import kye.expressions as ast
import pandas as pd

class Callable:
    """ Abstract class for callables """
    def call(self, arguments):
        raise NotImplementedError()

    def arity(self):
        raise NotImplementedError()

    def __str__(self):
        return "<callable>"

class Type(Callable):
    name: str
    edges: t.Dict[str, Edge]

    def test(self, value):
        raise NotImplementedError()
    
    def __str__(self) -> str:
        return self.name

class Abstract(Type):
    pass

class Number(Abstract):
    name = "Number"
    edges = {}

    def test(self, val):
        if isinstance(val, pd.Series):
            assert val.empty or pd.api.types.is_numeric_dtype(val)
        else:
            assert isinstance(val, (int, float))

    def arity(self):
        return 1

    def call(self, arguments):
        return float(arguments[0])

class String(Abstract):
    name = "String"
    edges = {}

    def test(self, val):
        if isinstance(val, pd.Series):
            assert val.empty or pd.api.types.is_string_dtype(val)
        else:
            assert isinstance(val, str)

    def arity(self):
        return 1

    def call(self, arguments):
        return str(arguments[0])

class Boolean(Abstract):
    name = "Boolean"
    edges = {}

    def test(self, val):
        if isinstance(val, pd.Series):
            assert val.empty or pd.api.types.is_bool_dtype(val)
        else:
            assert isinstance(val, bool)

    def arity(self):
        return 1

    def call(self, arguments):
        return bool(arguments[0])

def select(index: t.List[str], data: pd.DataFrame, keys: t.List[t.Any]) -> pd.DataFrame:
    assert len(index) == len(keys)
    for key, val in zip(index, keys):
        assert key in data.columns
        if isinstance(val, pd.Series):
            data = data[data[key].isin(val)]
        else:
            data = data[data[key] == val]
    return data

class Model(Type):
    name: str
    index: t.List[str]
    edges: t.Dict[str, Edge]
    data: pd.DataFrame

    def __init__(self, name: str, index: t.List[str], data: pd.DataFrame):
        self.name = name
        self.index = index
        self.data = data
        self.edges = {}
    
    def test(self, val):
        if len(self.index) != 1:
            raise NotImplementedError()
        selection = select(self.index, self.data, [val,])
        return not selection.empty
    
    def arity(self):
        return len(self.index)
    
    def call(self, arguments):
        selection = select(self.index, self.data, arguments)
        return SubModel(self, selection)
    
    def __str__(self):
        return self.data.__str__()

class SubModel(Model):
    parent: Model
    edges: t.Dict[str, Edge]
    data: pd.DataFrame

    def __init__(self, parent: Model, data: pd.DataFrame):
        self.parent = parent
        self.data = data
        self.edges = {**parent.edges}
    
    @property
    def name(self):
        return self.parent.name
    
    @property
    def index(self):
        return self.parent.index

class Edge(Callable):
    name: str
    model: Model
    params: t.List[str]
    cardinality: ast.Cardinality
    data: pd.Series
    type: Type
    bound: t.Optional[pd.Series]

    def __init__(self, name: str, model: Model, params: t.List[str], cardinality: ast.Cardinality, type: Type):
        self.name = name
        self.model = model
        self.params = params
        self.cardinality = cardinality
        self.type = type
        self.bound = None
    
    @property
    def edges(self):
        return self.type.edges
    
    def arity(self):
        return 1 + len(self.params)
    
    def call(self, arguments):
        assert len(arguments) == self.arity(), f"Expected {self.arity()} arguments, got {len(arguments)}"

        assert isinstance(arguments[0], Model)
        df = arguments[0].data
        
        if self.name not in df:
            return pd.Series(
                dtype='object',
                name=self.name,
                # Copy an empty version of the index
                index=df.index.drop(df.index)
            )
        val = df[self.name]
        
        if self.cardinality in (ast.Cardinality.ONE, ast.Cardinality.MORE):
            assert not val.isna().any()
        
        val = val.explode().dropna().infer_objects()

        if self.cardinality in (ast.Cardinality.ONE, ast.Cardinality.MAYBE):
            assert val.index.is_unique
        
        return val
    
    def bind(self, value: pd.Series):
        self.bound = value
        return self
    
    def __str__(self):
        if self.bound is not None:
            return self.bound.__str__()
        return f"{self.model.name}.{self.name}"

class Const(Type):
    val: t.Any
    type: Type

    def __init__(self, val: t.Any, type: Type):
        self.val = val
        self.type = type
    
    @property
    def name(self):
        return self.type.name
    
    @property
    def edges(self):
        return self.type.edges
    
    def test(self, value):
        self.type.test(value)
        if isinstance(value, pd.Series):
            assert (value == self.val).all()
        else:
            assert value == self.val
    
    def arity(self):
        return 0
    
    def call(self, arguments):
        return self.val