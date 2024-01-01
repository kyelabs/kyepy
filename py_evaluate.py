from __future__ import annotations
from duckdb import DuckDBPyRelation
import kye.types as Types

definitions = {
    'Type.$filter': '{} and {}',
    'String': 'type(value) is str',
    'String.length': 'len(value)',
    'Boolean': 'type(value) is bool',
    'Object.$eq': '{} == {}',
    'Object.$ne': '{} != {}',
    'Number': 'isinstance(value, (int,float))',
    'Number.$gt': '{} > {}',
    'Number.$lt': '{} < {}',
    'Number.$gte': '{} >= {}',
    'Number.$lte': '{} <= {}',
    'Boolean.$and': '{} and {}',
    'Boolean.$or': '{} or {}',
}

def to_py(expr: Types.Expression):
    args = []
    if isinstance(expr, Types.CallExpression):
        args = [ to_py(expr.bound), *(to_py(arg) for arg in expr.args) ]
        ref = expr.edge.ref
    if isinstance(expr, Types.TypeRefExpression):
        ref = expr.type.ref
    if isinstance(expr, Types.EdgeRefExpression):
        ref = expr.edge.ref
    if isinstance(expr, Types.LiteralExpression):
        return repr(expr.value)
    assert ref in definitions
    return definitions[ref].format(*args)

if __name__ == '__main__':
    import kye

    api = kye.compile('''
    type Name: String[length == 5]
    ''')
    py = to_py(api.models['Name'].expr)
    print(eval(py, {'value': 'hello'}))

    print(py)