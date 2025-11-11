import inspect
from contextlib import AbstractAsyncContextManager
from typing import Any, Callable, TypeVar

from .dimap import DIMap
from .factory_box import Factory

_T = TypeVar('_T')


class InstanceBox(AbstractAsyncContextManager):
    start_methods = ["__aenter__", "start", "__enter__"]
    close_methods = ["__aexit__", "aclose", "close", "__exit__"]

    def __init__(self):
        self._items = DIMap()

    def get_instance(self, cls: type[_T] | None, name: str | None = None) -> _T | None:
        match = self._items.find_match((cls, name))
        return match[0] if match is not None else None

    def register_instance(self, cls: type[_T] | None, name: str | None, value: _T) -> _T:
        self._items[(cls, name)] = value
        return value

    async def create_instance(self, cls: type[_T] | None, name: str | None, factory: Factory, **args) -> _T:
        existing_item = self._items.get((cls, name))
        if existing_item is not None:
            return existing_item
        new_instance = await self._start_instance(factory, args)
        self._items[(cls, name)] = new_instance
        return new_instance

    async def __aexit__(self, *args):
        await self.close()

    async def close(self):
        for instance in reversed(self._items.values()):
            await self._shutdown_instance(instance)
        self._items.clear()

    @staticmethod
    async def _start_instance(factory: Factory, args: dict) -> Any:
        instance = factory(**args)
        if inspect.isawaitable(instance):
            instance = await instance
        startup_method, _ = _lookup_method(instance, InstanceBox.start_methods)
        if startup_method is not None:
            startup_res = startup_method()
            if inspect.isawaitable(startup_res):
                await startup_res
        return instance

    @staticmethod
    async def _shutdown_instance(instance):
        close_method, close_method_name = _lookup_method(instance, InstanceBox.close_methods)
        if close_method is not None:
            if close_method_name.startswith("__"):  # __exit__/__aexit__
                res = close_method(None, None, None)
            else:
                res = close_method()
            if inspect.isawaitable(res):
                await res

def _lookup_method(obj, method_names) -> tuple[Callable | None, str]:
    for method_name in method_names:
        method = getattr(obj, method_name, None)
        if method is not None:
            return method, method_name
    return None, ""
