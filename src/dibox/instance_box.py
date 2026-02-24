import inspect
from typing import Any, Callable, TypeVar, cast

from .dimap import ArgNameQuery, DIMap, TypeQuery
from .factory_box import FactoryFunc

_T = TypeVar('_T')

class InstanceBox:
    """
    This class is responsible for creating, storing, and cleaning up objects. It ensures that each
    object is instantiated only once and can be retrieved by its type and/or name.
    As a context manager, oversees the startup and shutdown of managed objects.
    """
    start_methods = ["__aenter__", "start", "__enter__"]
    close_methods = ["__aexit__", "aclose", "close", "__exit__"]

    def __init__(self):
        self._items = DIMap[Any]()


    def get_instance(
        self,
        requested_type: TypeQuery[_T],
        name: ArgNameQuery = None
    ) -> _T | None:
        match = self._items.find_match(requested_type, name)
        return match[0] if match is not None else None

    async def create_instance(
        self,
        requested_type: TypeQuery[_T],
        name: ArgNameQuery,
        factory: FactoryFunc[_T],
        **args: Any
    ) -> _T:
        existing_item = self._items.get((requested_type, name))
        if existing_item is not None:
            return existing_item
        new_instance = await _start_instance(factory, args)
        self._items[(requested_type, name)] = new_instance
        return new_instance

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args: Any):
        await self.close()

    async def close(self):
        for instance in reversed(self._items.values()):
            await _shutdown_instance(instance)
        self._items.clear()

async def _start_instance(factory: FactoryFunc[_T], args: dict[str, Any]) -> _T:
    instance = factory(**args)
    if inspect.isawaitable(instance):
        instance = await instance
    startup_method, _ = _lookup_method(instance, InstanceBox.start_methods)
    if startup_method is not None:
        startup_res = startup_method()
        if inspect.isawaitable(startup_res):
            await startup_res
    return cast(_T, instance)

async def _shutdown_instance(instance: Any):
    close_method, close_method_name = _lookup_method(instance, InstanceBox.close_methods)
    if close_method is not None:
        if close_method_name.startswith("__"):  # __exit__/__aexit__
            res = close_method(None, None, None)
        else:
            res = close_method()
        if inspect.isawaitable(res):
            await res

def _lookup_method(obj: Any, method_names: list[str]) -> tuple[Callable[..., Any] | None, str]:
    for method_name in method_names:
        method = getattr(obj, method_name, None)
        if method is not None:
            return method, method_name
    return None, ""
