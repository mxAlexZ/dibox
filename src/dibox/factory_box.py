import inspect
from functools import partial
from typing import Awaitable, Callable, TypeVar, cast

from .dimap import DIMap, DIMapKey

_T = TypeVar('_T')

Factory = Callable[..., _T] | Callable[..., Awaitable[_T]]
TypeSelector = None | type[_T] | Callable[[type[_T]], bool]
MatchResult = tuple[Factory[_T], DIMapKey]

class FactoryBox:
    def __init__(self):
        self.map = DIMap[Factory]()
        self.func_bindings = []

    def bind(self, type_selector: TypeSelector[_T], factory: Factory[_T], *, argname: str | None = None, **kwargs):
        factory = cast(Factory[_T], factory if not kwargs else partial(factory, **kwargs))
        if _is_func_selector(type_selector):
            self.func_bindings.append((type_selector, factory))
            if argname is not None:
                raise ValueError("argname is not (yet) allowed when binding to a function")
        else:
            self.map[(cast(type, type_selector), argname)] = factory

    def get_factory(self, cls: type[_T] | None, argname: str | None) -> MatchResult[_T]:
        match = self.map.find_match((cls, argname))
        if match is not None:
            return match
        match = self._get_factory_from_func_bindings(cls)
        if match is not None:
            return match
        if not inspect.isclass(cls):
            raise ValueError("cls should be a class type")
        return cls, (cls, None)

    def _get_factory_from_func_bindings(self, cls: type[_T] | None) -> MatchResult[_T] | None:
        for type_selector, factory in self.func_bindings:
            if type_selector(cls):
                return factory, (cls, None)
        return None

def _is_func_selector(selector: TypeSelector) -> bool:
    return inspect.isfunction(selector) and len(inspect.signature(selector).parameters) == 1