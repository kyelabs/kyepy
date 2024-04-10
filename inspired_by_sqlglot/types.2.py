from __future__ import annotations
import typing as t

class Type:
    def __init__(self,
                 name: str = None,
                 dynamic: bool = False,
                 foreign: bool = False,
                 range: bool = False):
        self.name = name
        self.dynamic = dynamic
        self.foreign = foreign
        self.range = range
    
    def equals(self, other: Type) -> Type:
        r, c = None, None
        if self.range and not other.range:
            r, c = self, other
        if not self.range and other.range:
            r, c = other, self
        if r and c:
            if self.name != other.name:
                raise ValueError("Cannot compare two different types")
            return Type(
                name=r.name,
                dynamic=r.dynamic or c.dynamic,
                foreign=r.foreign or c.foreign,
                range=False)
        return self.compare(other)

    def compare(self, other: Type) -> Type:
        if self.range and other.range:
            raise ValueError("Cannot compare two range types")
        if not self.range and not other.range:
            return Type('Boolean',
                        dynamic=self.dynamic or other.dynamic,
                        foreign=self.foreign or other.foreign,
                        range=False)
        if self.name != other.name:
            raise ValueError("Cannot compare two different types")
        return Type(
            name=self.name,
            dynamic=self.dynamic or other.dynamic,
            foreign=self.foreign or other.foreign,
            range=True)