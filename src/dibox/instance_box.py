import inspect
from collections.abc import Mapping
from contextlib import AsyncExitStack
from typing import Any, Callable, TypeVar

from .binding_box import BindingRecord
from .dimap import ANY_ARG, DIMap, DIMapKey, TypeQuery, WildArgName, WildType

_T = TypeVar('_T')


class InstanceBox:
    """Stores created instances and manages their lifecycle.

    Instances are keyed by (type, name) and created via factory callables.
    On creation, startup hooks (`__aenter__`, `start`, `__enter__`) are called if present.
    On `close()`, shutdown hooks are called in reverse creation order.
    """
    start_methods = ["start"]
    close_methods = ["aclose", "close"]

    def __init__(self) -> None:
        self._items = DIMap[Any]()
        self._exit_stack = AsyncExitStack()

    @property
    def index(self) -> Mapping[DIMapKey[Any], Any]:
        """Read-only view of exact-keyed created instances."""
        return self._items

    def get_instance(
        self,
        requested_type: TypeQuery[_T],
        name: WildArgName = ANY_ARG
    ) -> _T | None:
        matched_instance, _ = self._items.find_match(requested_type, name)
        return matched_instance

    async def create_instance(
        self,
        requested_type: WildType[_T],
        name: WildArgName,
        binding_record: BindingRecord,
        **args: Any
    ) -> _T:
        factory_result = await binding_record.call_async(**args) # this can be a context manager instance
        instance = await self._start_instance(factory_result)
        self._items[(requested_type, name)] = instance
        return instance

    async def close(self, exc_details: tuple[Any, Any, Any] = (None, None, None)) -> None:
        # __aexit__ return values is intentionally ignored:
        #  no single object can suppress an exception on behalf of the whole container
        await self._exit_stack.__aexit__(*exc_details)
        self._items.clear()

    async def _start_instance(self, instance: Any) -> Any:
        if hasattr(instance, "__aenter__"):
            return await self._exit_stack.enter_async_context(instance)
        if hasattr(instance, "__enter__"):
            return self._exit_stack.enter_context(instance)
        await self._start_and_register_close(instance)
        return instance

    async def _start_and_register_close(self, instance: Any) -> None:
        startup_method = _lookup_method(instance, self.start_methods)
        if startup_method is not None:
            if inspect.iscoroutinefunction(startup_method):
                await startup_method()
            else:
                startup_method()
        shutdown_method = _lookup_method(instance, self.close_methods)
        if shutdown_method is not None:
            if inspect.iscoroutinefunction(shutdown_method):
                self._exit_stack.push_async_callback(shutdown_method)
            else:
                self._exit_stack.callback(shutdown_method)


def _lookup_method(obj: object, method_names: list[str]) -> Callable[..., object] | None:
    for method_name in method_names:
        method: Callable[..., object] | None = getattr(obj, method_name, None)
        if method is not None:
            return method
    return None
