from __future__ import annotations
import pandas as pd

import kye.type.types as typ
import kye.parse.expressions as ast

NATIVE_TYPES: typ.Types = {}

def edge(output, allows_null=False, allows_many=False):
    def edge_wrapper(fn):
        fn.__edge__ = {
            'allows_null': allows_null,
            'allows_many': allows_many,
            'output': output,
        }
        return fn
    return edge_wrapper

class NativeType:
    def __init_subclass__(cls) -> None:
        parent = cls.__mro__[1].__name__
        if parent == 'NativeType':
            this = typ.Type(name=cls.__name__, source=None)
        else:
            this = NATIVE_TYPES[parent].clone()
            this.name = cls.__name__
        NATIVE_TYPES[this.name] = this
        for name, method in cls.__dict__.items():
            if hasattr(method, '__edge__'):
                edge_attr = method.__edge__
                this.define(typ.Edge(
                    name=name,
                    title=None,
                    indexes=typ.Indexes([]),
                    allows_null=edge_attr['allows_null'],
                    allows_many=edge_attr['allows_many'],
                    model=this,
                    returns=NATIVE_TYPES[edge_attr['output']],
                    expr=None,
                    loc=None,
                ))

class Boolean(NativeType):
    pass

class Number(NativeType):
    pass

class Integer(Number):
    pass

class String(NativeType):
    def __assert__(self, this: pd.Series):
        assert isinstance(this, str), f"Expected string, got {this!r}"
    
    @edge(output='Number')
    def length(self, this):
        return len(this)