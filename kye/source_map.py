from enum import Enum
from dataclasses import dataclass
import typing as t
import struct
from base64 import b64encode, b64decode

class ItemType(Enum):
    MODEL = 0
    INDEX = 1
    EDGE = 2
    ASSERTION = 3
    CMD = 4

class ByteReader:
    def __init__(self, bytes):
        self.bytes = bytes
        self.offset = 0
    
    def raise_if_short(self, size):
        if self.offset + size > len(self.bytes):
            raise ValueError('Not enough bytes to read')
    
    def read_int(self, size):
        self.raise_if_short(size)
        result = int.from_bytes(self.bytes[self.offset:self.offset + size], 'big')
        self.offset += size
        return result
    
    def read_str(self, size):
        self.raise_if_short(size)
        result = self.bytes[self.offset:self.offset + size].decode('utf-8')
        self.offset += size
        return result
    
    @property
    def empty(self):
        return self.offset >= len(self.bytes)

class SourceMapWriter:
    def __init__(self):
        self.models = {}
        self.model = None
    
    def add_model(self, model_name, loc):
        self.models[model_name] = {
            'loc': loc,
            'indexes': [],
            'edges': {},
            'assertions': [],
        }
        self.model = self.models[model_name]
    
    def add_index(self, continue_index, loc):
        assert self.model is not None
        if not continue_index:
            self.model['indexes'].append([])
        self.model['indexes'][-1].append(loc)
    
    def add_edge(self, edge_name, loc):
        assert self.model is not None
        self.model['edges'][edge_name] = loc
    
    def add_assertion(self, loc):
        assert self.model is not None
        self.model['assertions'].append({'loc': loc, 'expr': []})
    
    def add_cmd(self, loc):
        assert self.model is not None
        self.model['assertions'][-1]['expr'].append(loc)

def read_source_map(bytes):
    stream = ByteReader(bytes)
    source_map = SourceMapWriter()
    line = 0
    col = 0
    
    while not stream.empty:
        header = stream.read_int(1)
        type = ItemType(header >> 4)
        line_size = 2 ** ((header & 0x8) >> 3)
        col_size = 2 ** ((header & 0x4) >> 2)
        key_size = 2 ** (header & 0x3)

        line_inc = stream.read_int(line_size)
        col_inc = stream.read_int(col_size)
        if line_inc == 0:
            col += col_inc
        else:
            line += line_inc
            col = col_inc

        loc = line, col
        if type == ItemType.MODEL:
            model_name = stream.read_str(stream.read_int(key_size))
            source_map.add_model(model_name, loc)
        elif type == ItemType.EDGE:
            edge_name = stream.read_str(stream.read_int(key_size))
            source_map.add_edge(edge_name, loc)
        elif type == ItemType.INDEX:
            source_map.add_index(key_size == 1, loc)
        elif type == ItemType.ASSERTION:
            source_map.add_assertion(loc)
        elif type == ItemType.CMD:
            source_map.add_cmd(loc)
        else:
            raise ValueError('Unknown item type')

    return source_map.models

stream = (
    b'\x00\x01\x00\x04User'
    b'\x11\x00\x06'
    b'\x10\x00\x04'
    b'\x11\x00\x06'
    b'\x20\x01\x02\x02id'
    b'\x30\x01\x02'
    b'\x40\x00\x04'
)

print(b64encode(stream))
print(read_source_map(stream))