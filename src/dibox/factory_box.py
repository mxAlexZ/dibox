import inspect
from functools import partial
from types import UnionType
from typing import Awaitable, Callable, TypeVar, cast

from .dimap import DIMapKey, _DIMap

_T = TypeVar('_T')

FactoryFunc = Callable[..., _T] | Callable[..., Awaitable[_T]]
TypeSelector = None | type[_T] | Callable[[type[_T]], bool]
MatchResult = tuple[FactoryFunc[_T], DIMapKey[_T]]
TypeRequest = type[_T] | UnionType

class _FactoryBox:
    """
    A container for managing factory functions.
    It supports two types of bindings:
    - Direct type-to-factory mappings with optional argument names
    - Function-based selectors that dynamically match types
    """
    def __init__(self):
        self.map = _DIMap[FactoryFunc]()
        self.func_bindings = []

    def bind(self, type_selector: TypeSelector[_T], factory: FactoryFunc[_T], *, argname: str | None = None, **kwargs):
        factory = cast(FactoryFunc[_T], factory if not kwargs else partial(factory, **kwargs))
        if _is_func_selector(type_selector):
            self.func_bindings.append((type_selector, factory))
            if argname is not None:
                raise ValueError("argname is not (yet) allowed when binding to a function")
        else:
            self.map[(cast(type, type_selector), argname)] = factory

    def get_factory(self, cls: TypeRequest[_T] | None, argname: str | None) -> MatchResult[_T]:
        match = self.map.find_match((cls, argname))
        if match is not None:
            return match
        match = self._get_factory_from_func_bindings(cls)
        if match is not None:
            return match
        if not inspect.isclass(cls):
            raise ValueError("cls should be a class type")
        return cls, (cls, None)

    def _get_factory_from_func_bindings(self, cls: TypeRequest[_T] | None) -> MatchResult[_T] | None:
        for type_selector, factory in self.func_bindings:
            if type_selector(cls):
                return factory, (cls, None)
        return None

def _is_func_selector(selector: TypeSelector) -> bool:
    return inspect.isfunction(selector) and len(inspect.signature(selector).parameters) == 1