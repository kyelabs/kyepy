from __future__ import annotations
import ibis

import kye.types as typ
import kye.expressions as ast

NATIVE_TYPES: typ.Types = {}

def type():
    def type_wrapper(cls):
        this = typ.Type(name=cls.__name__, source=None)
        assert this.name not in NATIVE_TYPES, f"Type {this.name} already defined"
        NATIVE_TYPES[this.name] = this
        for name, method in cls.__dict__.items():
            if hasattr(method, '__edge__'):
                edge_attr = method.__edge__
                this.define(typ.Edge(
                    name=name,
                    indexes=typ.Indexes([]),
                    allows_null=edge_attr['allows_null'],
                    allows_many=edge_attr['allows_many'],
                    input=this,
                    output=NATIVE_TYPES[edge_attr['output']],
                    expr=ast.NativeCall(method),
                ))
        return cls
    return type_wrapper
        

def edge(output, allows_null=False, allows_many=False):
    def edge_wrapper(fn):
        fn.__edge__ = {
            'allows_null': allows_null,
            'allows_many': allows_many,
            'output': output,
        }
        return fn
    return edge_wrapper

@type()
class Boolean:
    pass

@type()
class Number:
    pass

@type()
class String:
    def __assert__(self, this: ibis.Value):
        assert isinstance(this, str), f"Expected string, got {this!r}"
    
    @edge(output='Number')
    def length(self, this):
        return len(this)