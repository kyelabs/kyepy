from kye.parser.environment import Environment
import kye.parser.kye_ast as AST
from kye.parser.types import Type, Edge

def evaluate_type_expression(ast: AST.Expression, env: Environment) -> Type:
    if isinstance(ast, AST.Identifier):
        typ = env.lookup(ast.name)
        if typ is None:
            raise Exception(f'Undefined Type: {repr(ast)}')
        return typ.type
    
    if isinstance(ast, AST.LiteralExpression):
        base_type = None
        if type(ast.value) is str:
            base_type = 'String'
        if isinstance(ast.value, (float, int)):
            base_type = 'Number'
        assert base_type is not None
        return Type(
            extends=env.root.get_child(base_type).type,
            filters={'eq': ast.value},
        )
    
    raise NotImplementedError(f'Not Implemented {ast.__class__.__name__}')

def evaluate_edge(ast: AST.EdgeDefinition, env: Environment) -> Edge:
    return Edge(
        name=ast.name,
        returns=evaluate_type_expression(ast.type, env),
        nullable=ast.cardinality in ('?','*'),
        multiple=ast.cardinality in ('+','*'),
    )

def evaluate(ast: AST.AST, env: Environment) -> Type:
    if isinstance(ast, AST.Expression):
        return evaluate_type_expression(ast, env)
    
    if isinstance(ast, AST.AliasDefinition):
        return Type(
            name=ast.name,
            extends=evaluate_type_expression(ast.type, env),
        )

    if isinstance(ast, AST.EdgeDefinition):
        return evaluate_type_expression(ast.type, env)
    
    if isinstance(ast, AST.ModelDefinition):
        return Type(
            name=ast.name,
            indexes=ast.indexes,
            edges={
                edge.name: evaluate_edge(edge, env)
                for edge in ast.edges
            }
        )