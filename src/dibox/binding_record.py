import inspect
from functools import partial
from typing import Any, Awaitable, Callable


class BindingRecord:
    __slots__ = ("name", "_factory", "_is_async")

    def __init__(self, factory: Callable[..., Awaitable[Any]] | Callable[..., Any], name: str | None = None) -> None:
        self.name = name or getattr(factory, "__name__", None) or str(factory)
        self._factory = factory
        self._is_async = inspect.iscoroutinefunction(factory)

    @property
    def signature(self) -> inspect.Signature:
        return inspect.signature(self._factory)

    def call_sync(self, *args: Any, **kwargs: Any) -> Any:
        if self._is_async:
            raise RuntimeError("synchronous calls are not supported")
        else:
            return self._factory(*args, **kwargs)

    async def call_async(self, *args: Any, **kwargs: Any) -> Any:
        if self._is_async:
            return await self._factory(*args, **kwargs)
        else:
            return self._factory(*args, **kwargs)

    def partial(self, binding_name: str, args: tuple[Any], kwargs: dict[str, Any] = {}) -> "BindingRecord":
        new_factory = partial(self._factory, *args, **kwargs)
        return BindingRecord(new_factory, name=binding_name)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"BindingRecord(name={self.name!r})"
