from kye.parser.environment import Environment, ChildEnvironment
import kye.parser.kye_ast as AST
from kye.parser.types import Model, Type, Edge, Expression

def evaluate_expression(ast: AST.Expression, env: Environment) -> Expression:
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
        return env.root.get_child(base_type).type.select(ast.value)
    
    if isinstance(ast, AST.Operation):
        # TODO: There must be a way to have the type define it's own
        # filter operation right?
        # Would that require re-assigning environments to the ast or something?
        if ast.name == 'filter':
            typ = evaluate(ast.children[0], env)
            if len(ast.children) == 0:
                return typ
            return typ.extend(
                filter=evaluate_expression(ast.children[1], typ.env)
            )
        if ast.name == 'dot':
            typ = evaluate(ast.children[0])
            
    
    raise NotImplementedError(f'Not Implemented {ast.__class__.__name__}')

def evaluate(ast: AST.AST, env: Environment) -> Type:
    if isinstance(ast, AST.Expression):
        return evaluate_expression(ast, env)
    
    if isinstance(ast, AST.AliasDefinition):
        return evaluate_expression(ast.type, env)

    if isinstance(ast, AST.EdgeDefinition):
        return evaluate_expression(ast.type, env)
    
    if isinstance(ast, AST.ModelDefinition):
        typ = Model(
            name=ast.name,
            indexes=ast.indexes,
        )
        for edge in ast.edges:
            typ.edges[edge.name] = Edge(
                owner=typ,
                name=edge.name,
                returns=evaluate_expression(edge.type, env),
                nullable=edge.cardinality in ('?','*'),
                multiple=edge.cardinality in ('+','*'),
            )
        return typ