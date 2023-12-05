import kye.parser.kye_ast as AST

def compile_type_expression(ast: AST.Expression, typ: dict):
    assert isinstance(ast, AST.Expression)
    if isinstance(ast, AST.Identifier):
        assert ast.name[0].isupper()
        typ['type'] = ast.name
    elif isinstance(ast, AST.LiteralExpression):
        typ['const'] = ast.value
    elif isinstance(ast, AST.Operation):
        if ast.name == 'filter':
            assert isinstance(ast.children[0], AST.Identifier)
            assert len(ast.children) <= 2
            typ['type'] = ast.children[0].name
            if len(ast.children) == 2:
                typ['filter'] = ast.children[1].meta.text
        else:
            typ['expr'] = ast.meta.text
    else:
        raise Exception('Unknown Expression')

def compile_edge(ast: AST.EdgeDefinition, edges: dict):
    assert isinstance(ast, AST.EdgeDefinition)
    edge = {}
    edges[ast.name] = edge
    if ast.cardinality in ('?','*'):
        edge['nullable'] = True
    if ast.cardinality in ('+','*'):
        edge['multiple'] = True
    compile_type_expression(ast.type, edge)

def compile_alias(ast: AST.AliasDefinition, models: dict, path: tuple[str]):
    assert isinstance(ast, AST.AliasDefinition)
    alias = {}
    path += (ast.name,)
    models['.'.join(path)] = alias
    compile_type_expression(ast.type, alias)

def compile_model(ast: AST.ModelDefinition, models: dict, path: tuple[str]):

    def compile_index(index: list[str]):
        assert len(index) >= 1
        if len(index) == 1:
            return index[0]
        return index

    assert isinstance(ast, AST.ModelDefinition)
    path += (ast.name,)
    model = { 'edges': {} }

    assert len(ast.indexes) >= 1
    if len(ast.indexes) == 1:
        model['index'] = compile_index(ast.indexes[0])
    else:
        model['indexes'] = [compile_index(idx) for idx in ast.indexes]
    
    for subtype in ast.subtypes:
        compile_type_definition(subtype, models, path)
    for edge in ast.edges:
        compile_edge(edge, model['edges'])
    models['.'.join(path)] = model

def compile_type_definition(ast: AST.TypeDefinition, models: dict, path: tuple[str]):
    assert isinstance(ast, AST.TypeDefinition)
    if isinstance(ast, AST.AliasDefinition):
        compile_alias(ast, models, path)
    elif isinstance(ast, AST.ModelDefinition):
        compile_model(ast, models, path)
    else:
        raise Exception('Unknown TypeDefinition')

def compile_ast(ast: AST.AST):
    if isinstance(ast, AST.Expression):
        return ast.meta.text
    if isinstance(ast, AST.ModuleDefinitions):
        models = {}
        for definition in ast.children:
            compile_type_definition(definition, models, tuple())
        return models