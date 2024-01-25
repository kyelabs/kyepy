from __future__ import annotations
from typing import TYPE_CHECKING

import kye.compiler.compiled as Compiled

if TYPE_CHECKING:
    from kye.compiler.models import Models, Type, TYPE_REF

def models_from_compiled(types: Models, source) -> Models:
    source = Compiled.Models(**source)

    # 1. Do first iteration creating a stub type for each name
    for ref in source.models:
        types.define(ref)
    
    zipped_source_and_stub: dict[TYPE_REF, tuple[Compiled.Type, Type]] = {
        ref: (src, types[ref])
        for ref, src in source.models.items()
    }

    # 2. During second iteration define the edges, indexes & assertions
    for src, typ in zipped_source_and_stub.values():

        for edge_name, edge_type_ref in src.edges.items():
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

        for assertion in src.assertions:
            typ.define_assertion(
                op=assertion.op,
                arg=assertion.arg,
            )

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

    return types