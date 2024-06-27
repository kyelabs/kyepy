from enum import Enum, auto

class OP(Enum):
    LOAD_COL =   auto(), 0, 'str'

    # Unary
    IS_NULL =    auto(), 1
    NOT_NULL =   auto(), 1
    NOT =        auto(), 1 # boolean not
    NEG =        auto(), 1 # arithmetic negation

    # Binary
    NE =         auto(), 2
    EQ =         auto(), 2
    OR  =        auto(), 2
    AND =        auto(), 2
    LT =         auto(), 2
    GT =         auto(), 2
    LTE =        auto(), 2
    GTE =        auto(), 2
    ADD =        auto(), 2
    SUB =        auto(), 2
    MUL =        auto(), 2
    DIV =        auto(), 2
    MOD =        auto(), 2
    
    # Binary with constant
    NE_CONST =   auto(), 1, 'any'
    EQ_CONST =   auto(), 1, 'any'
    LT_CONST =   auto(), 1, 'any'
    GT_CONST =   auto(), 1, 'any'
    LTE_CONST =  auto(), 1, 'any'
    GTE_CONST =  auto(), 1, 'any'
    ADD_CONST =  auto(), 1, 'num'
    SUB_CONST =  auto(), 1, 'num'
    MUL_CONST =  auto(), 1, 'num'
    DIV_CONST =  auto(), 1, 'num'
    MOD_CONST =  auto(), 1, 'num'

    # Aggregates
    NUNIQUE =    auto(), 1
    
    @property
    def code(self):
        return self.value[0]
    
    @property
    def num_stack_args(self):
        return self.value[1]
    
    @property
    def signature(self):
        return self.value[2:]
    
    @property
    def arity(self):
        return len(self.signature)
    
    def matches_signature(self, args):
        if len(args) != len(self.signature):
            return False
        for arg, sig_arg in zip(args, self.signature):
            if sig_arg == 'any':
                if not isinstance(arg, (int, float, str)):
                    return False
            elif sig_arg == 'num':
                if not isinstance(arg, (int, float)):
                    return False
            elif sig_arg == 'str':
                if not isinstance(arg, str):
                    return False
            else:
                raise ValueError(f'Invalid signature: {sig_arg}')
        return True

def parse_command(cmd) -> tuple[OP, tuple]:
    op = None
    args = None
    if isinstance(cmd, str):
        op = OP[cmd.upper()]
        assert op.arity == 0
        args = tuple()
    elif isinstance(cmd, dict):
        assert len(cmd) == 1
        cmd, args = list(cmd.items())[0]
        assert isinstance(cmd, str)
        if isinstance(args, list):
            args = tuple(args)
        elif args is None:
            args = tuple()
        else:
            assert isinstance(args, (str, int, float))
            args = (args,)
        op = OP[cmd.upper()]
    else:
        raise ValueError(f'Invalid command: {cmd}')
    assert op.matches_signature(args)
    return op, args