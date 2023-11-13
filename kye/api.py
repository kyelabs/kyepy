from __future__ import annotations
from functools import cached_property
from typing import Any
import kye.parser.parser as parser
from kye.compiled import CompiledDataset
from kye.dataset import Models
from kye.loader.loader import Loader
from kye.validate import Validate

class ModelApi:
    def __init__(self, api: Api, model_name: str):
        self.api = api
        self.model_name = model_name
    
    def from_records(self, json):
        assert not self.api.done_loading, 'Cannot call from_records after loading is done'
        self.api.loader.from_json(self.model_name, json)

class Api:
    def __init__(self, text):
        self.compiled = parser.compile(text)
        self.models = Models(CompiledDataset(models=self.compiled))
        self.loader = Loader(self.models)
        self.done_loading = False

        for model_name in self.compiled.keys():
            if '.' not in model_name:
                setattr(self, model_name, ModelApi(self, model_name))
    
    @cached_property
    def validate(self):
        self.done_loading = True
        return Validate(self.loader)
    
    @property
    def errors(self):
        return set(self.validate.errors.aggregate(f"rule_ref, error_type").fetchall())

    @property
    def tables(self):
        return self.validate.tables

    def is_valid(self):
        return self.validate.is_valid()
    
    def from_records(self, model_name: str, json: Any):
        getattr(self, model_name).from_records(json)
        return self

def compile(text) -> Api:
    return Api(text)