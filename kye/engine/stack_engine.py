from __future__ import annotations
import pandas as pd
import numpy as np
import inspect
from functools import wraps
from typing import Literal

class Stack:
    index: pd.Index
    stack: list[pd.Series]
    errors: pd.Series

    def __init__(self, index):
        self.index = index
        self.stack = []
        self.keep = pd.Series(True, index=self.index, dtype=bool)
        self.errors = pd.Series(index=index, dtype=str)
    
    @property
    def empty(self):
        """ Whether the stack has no current values """
        return len(self.stack) == 0

    def __len__(self):
        return len(self.stack)
    
    def dup(self):
        """ Duplicate the top value of the stack """
        assert not self.empty
        self.stack.append(self.stack[-1])
        return self
    
    def pop(self):
        """ Pop the top column off of the stack """
        assert not self.empty
        return self.stack.pop().loc[self.keep]
    
    def peek(self):
        """ Peek at the top value of the stack """
        assert not self.empty
        return self.stack[-1].loc[self.keep]

    def push(self, col: pd.Series):
        """ Push a column onto the stack """
        if col.dtype == 'object':
            col = col.explode().dropna().infer_objects()
        assert col.index.isin(self.index).all()
        self.stack.append(col)
        return self
    
    def assert_(self, error_type):
        """ Pop boolean column off of the stack
        the rows with a false value will be assert_ed out
        and get tagged with the error_type
        """
        is_valid = self.pop()
        assert pd.api.types.is_bool_dtype(is_valid)
        is_valid = is_valid.reindex(self.index).fillna(True)
        self.keep &= is_valid
        self.errors.loc[~is_valid] = error_type
        return self
    
    def lookup(self, other: pd.Series):
        """ Pop a column off of the stack and use it to lookup values in another column """
        n = self.pop().rename('key').to_frame()
        self.push(n.join(other.rename('val'), on='key').val)
        return self

    def and_(self):
        """ Pop two boolean columns off of the stack and compute their logical `and` """
        self.push(self.pop() & self.pop())
        return self

    def or_(self):
        """ Pop two boolean columns off of the stack and compute their logical `or` """
        self.push(self.pop() | self.pop())
        return self
    
    def not_(self):
        """ Pop a boolean column off of the stack and compute its logical `not` """
        self.push(~self.pop())
        return self

    def xor(self):
        """ Pop two boolean columns off of the stack and compute their logical `xor` """
        self.push(self.pop() ^ self.pop())
        return self
    
    def eq_const(self, const):
        """ Pop column off of the stack and compute whether it is equal to a constant """
        self.push(self.pop() == const)
        return self

    def ne_const(self, const):
        """ Pop column off of the stack and compute whether it is not equal to a constant """
        self.push(self.pop() != const)
        return self
    
    def lt_const(self, const):
        """ Pop column off of the stack and compute whether it is less than a constant """
        self.push(self.pop() < const)
        return self
    
    def le_const(self, const):
        """ Pop column off of the stack and compute whether it is less than or equal to a constant """
        self.push(self.pop() <= const)
        return self
    
    def gt_const(self, const):
        """ Pop column off of the stack and compute whether it is greater than a constant """
        self.push(self.pop() > const)
        return self
    
    def ge_const(self, const):
        """ Pop column off of the stack and compute whether it is greater than or equal to a constant """
        self.push(self.pop() >= const)
        return self
    
    def eq(self):
        """ Pop two columns off of the stack and compute whether they are equal """
        self.push(self.pop() == self.pop())
        return self
    
    def ne(self):
        """ Pop two columns off of the stack and compute whether they are not equal """
        self.push(self.pop() != self.pop())
        return self
    
    def lt(self):
        """ Pop two columns off of the stack and compute whether the first is less than the second """
        self.push(self.pop() < self.pop())
        return self
    
    def le(self):
        """ Pop two columns off of the stack and compute whether the first is less than or equal to the second """
        self.push(self.pop() <= self.pop())
        return self
    
    def gt(self):
        """ Pop two columns off of the stack and compute whether the first is greater than the second """
        self.push(self.pop() > self.pop())
        return self
    
    def ge(self):
        """ Pop two columns off of the stack and compute whether the first is greater than or equal to the second """
        self.push(self.pop() >= self.pop())
        return self
    
    def add(self):
        """ Pop two columns off of the stack and compute their sum """
        self.push(self.pop() + self.pop())
        return self
    
    def sub(self):
        """ Pop two columns off of the stack and compute their difference """
        self.push(self.pop() - self.pop())
        return self
    
    def mul(self):
        """ Pop two columns off of the stack and compute their product """
        self.push(self.pop() * self.pop())
        return self
    
    def div(self):
        """ Pop two columns off of the stack and compute their quotient """
        self.push(self.pop() / self.pop())
        return self
    
    def mod(self):
        """ Pop two columns off of the stack and compute their modulo """
        self.push(self.pop() % self.pop())
        return self
    
    def add_const(self, const):
        """ Pop column off of the stack and add a constant """
        self.push(self.pop() + const)
        return self
    
    def sub_const(self, const):
        """ Pop column off of the stack and subtract a constant """
        self.push(self.pop() - const)
        return self
    
    def mul_const(self, const):
        """ Pop column off of the stack and multiply by a constant """
        self.push(self.pop() * const)
        return self
    
    def div_const(self, const):
        """ Pop column off of the stack and divide by a constant """
        self.push(self.pop() / const)
        return self
    
    def mod_const(self, const):
        """ Pop column off of the stack and modulo by a constant """
        self.push(self.pop() % const)
        return self
    
    def all(self):
        """ Pop a boolean column off of the stack and compute whether all values are true """
        self.push(self.pop().groupby(level=0).all())
        return self

    def any(self):
        """ Pop a boolean column off of the stack and compute whether any values are true """
        self.push(self.pop().groupby(level=0).any())
        return self
    
    def sum(self):
        """ Pop a column off of the stack and compute its sum """
        self.push(self.pop().groupby(level=0).sum())
        return self
    
    def avg(self):
        """ Pop a column off of the stack and compute its mean """
        self.push(self.pop().groupby(level=0).mean())
        return self
    
    def min(self):
        """ Pop a column off of the stack and compute its minimum """
        self.push(self.pop().groupby(level=0).min())
        return self
    
    def max(self):
        """ Pop a column off of the stack and compute its maximum """
        self.push(self.pop().groupby(level=0).max())
        return self
    
    def cnt(self):
        """ Pop a column off of the stack and compute its count """
        self.push(self.pop().groupby(level=0).nunique().reindex(self.index, fill_value=0))
        return self
    
    def __repr__(self):
        return repr(pd.DataFrame({
            **({
                i:col if col.index.is_unique else col.groupby(level=0).unique()
                for i, col in enumerate(self.stack)
            }),
            'keep': self.keep,
            'errors': self.errors,
        }, index=self.index))

if __name__ == "__main__":
    df = pd.DataFrame({
        'a': [[0,1], np.nan, [3], [1,2,8]],
        'b': [4, 1, 6, 7],
    })
    to_letter = pd.Series([['a1','a2'],'b','c','d']).explode().dropna().infer_objects()
    stack = Stack(df.index)

    stack.push(df.a)
    stack.dup().lookup(to_letter)
    # stack.dup().cnt().eq_const(1).assert_('count(a) == 1')
    # stack.dup().ge_const(1).assert_('a >= 1')
    # stack.dup().lt_const(3).assert_('a < 3')
    # stack.dup().push(df.b).lt().assert_('a < b')
    print(stack)