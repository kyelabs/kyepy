from kye.compiler.types import TYPE_REF, EDGE, Type, Models


def from_json(source) -> Models:
    types = Models()

    # 1. Do first iteration creating a stub type for each name
    for ref in source.get('models',{}):
        types.define(ref)
    
    zipped_source_and_stub: dict[TYPE_REF, tuple[dict, Type]] = {
        ref: (src, types[ref])
        for ref, src in source.get('models',{}).items()
    }

    # 2. During second iteration define the edges, indexes & assertions
    for src, typ in zipped_source_and_stub.values():

        for edge_name, edge_type_ref in src.get('edges', {}).items():
            nullable = edge_name.endswith('?') or edge_name.endswith('*')
            multiple = edge_name.endswith('+') or edge_name.endswith('*')
            edge_name = edge_name.rstrip('?+*')
            typ.define_edge(
                name=edge_name,
                type=types[edge_type_ref],
                nullable=nullable,
                multiple=multiple,
            )

        if 'index' in src:
            typ.define_index(src['index'])
        if 'indexes' in src:
            for idx in src['indexes']:
                typ.define_index(idx)

        for assertion in src.get('assertions', []):
            typ.define_assertion(assertion)

    # 3. Wait till the third iteration to define the extends
    # so that parent edges & assertions will be known
    def recursively_define_parent(type_ref):
        src, typ = zipped_source_and_stub[type_ref]
        if 'extends' in src:
            parent = types[src['extends']]
            recursively_define_parent(parent.ref)
            typ.define_parent(parent)

    for type_ref in zipped_source_and_stub.keys():
        recursively_define_parent(type_ref)
    

    # # 4. Now that all edges have been defined, parse the expressions
    # for src, typ in zipped_source_and_stub:
    #     for assertion in src.get('assertions', []):
    #         # TODO: parse the assertion and add type information
    #         typ.define_assertion(assertion)

    return types