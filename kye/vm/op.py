from enum import Enum, auto

class OP(Enum):
    COL =        auto(), 1, 'str' # Load column

    # Type conversion
    STR =        auto(), 1 # Convert to string

    # Unary
    NA =    auto(), 1
    DEF =   auto(), 1
    NOT =        auto(), 1 # boolean not
    NEG =        auto(), 1 # arithmetic negation
    LEN =        auto(), 1 # length of string

    # Binary
    NE =         auto(), 2, 'any'
    EQ =         auto(), 2, 'any'
    OR  =        auto(), 2, 'bool'
    AND =        auto(), 2, 'bool'
    LT =         auto(), 2, 'any'
    GT =         auto(), 2, 'any'
    LE =         auto(), 2, 'any'
    GE =         auto(), 2, 'any'
    ADD =        auto(), 2, 'num'
    SUB =        auto(), 2, 'num'
    MUL =        auto(), 2, 'num'
    DIV =        auto(), 2, 'num'
    MOD =        auto(), 2, 'num'
    CONCAT =     auto(), 2, 'str'

    # Aggregates
    COUNT =      auto(), 1
    
    @property
    def code(self):
        return self.value[0]
    
    @property
    def arity(self):
        return self.value[1]
    
    @property
    def signature(self):
        return self.value[2:]
    
    def matches_signature(self, args):
        if len(args) > len(self.signature):
            return False
        for arg, sig_arg in zip(args, self.signature):
            if sig_arg == 'any':
                if not isinstance(arg, (int, float, str)):
                    return False
            elif sig_arg == 'num':
                if not isinstance(arg, (int, float)):
                    return False
            elif sig_arg == 'bool':
                if not isinstance(arg, bool):
                    return False
            elif sig_arg == 'str':
                if not isinstance(arg, str):
                    return False
            else:
                raise ValueError(f'Invalid signature: {sig_arg}')
        return True

def parse_command(cmd) -> tuple[OP, list]:
    op = None
    args = []
    if isinstance(cmd, str):
        op = OP[cmd.upper()]
    elif isinstance(cmd, dict):
        assert len(cmd) == 1
        cmd, args = list(cmd.items())[0]
        assert isinstance(cmd, str)
        op = OP[cmd.upper()]
        if not isinstance(args, list):
            if args is None:
                args = []
            else:
                assert isinstance(args, (str, int, float))
                args = [args]
    else:
        raise ValueError(f'Invalid command: {cmd}')
    assert op.matches_signature(args)
    return op, args