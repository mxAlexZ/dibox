import inspect
from enum import StrEnum
from functools import update_wrapper
from typing import Any, Awaitable, Callable, Iterable, Protocol, TypeVar, cast, overload

from .annotations import get_injected_params, remove_params_from_signature
from .container_protocol import ContainerProtocol

_R = TypeVar("_R")

MaybeAwaitableCallable = Callable[..., _R] | Callable[..., Awaitable[_R]]
ContainerResolver = Callable[[], ContainerProtocol]

class InjectDecoratorProtocol(Protocol):
    def __call__(self, func: Callable[..., _R]) -> Callable[..., _R]: ...


class SignatureModification(StrEnum):
    """
    Specifies how the inject decorator modifies the decorated function's signature:
    whether to set injected parameters as optional or to remove them from the signature.
    This is not yet implemented! Keeping it here for future consideration.
    """
    REMOVE_INJECTED = "remove_injected"
    KEEP_ALL = "keep_all"


class Injector:
    __slots__ = ("_decorator",)

    @overload
    def __init__(self, container: ContainerProtocol) -> None: ...
    @overload
    def __init__(self, *, container_resolver: ContainerResolver) -> None: ...

    def __init__(
        self, container: ContainerProtocol | None = None, *, container_resolver: ContainerResolver | None = None
    ) -> None:
        get_container = container_resolver if container_resolver is not None else lambda: cast(ContainerProtocol, container)
        self._decorator = _make_decorator(get_container)

    def __call__(self, func: Callable[..., _R]) -> Callable[..., _R]:
        return self.inject(func)

    def inject(self, func: Callable[..., _R]) -> Callable[..., _R]:
        return self._decorator(func)


def _params_to_inject(
    injected_params: dict[str, type],
    kwds: dict[str, Any],
) -> Iterable[tuple[str, type]]:
    for name, t in injected_params.items():
        if name not in kwds:
            yield name, t

def _make_wrapper(
    func: MaybeAwaitableCallable[Any],
    get_container: ContainerResolver,
    injected_params: dict[str, type],
) -> MaybeAwaitableCallable[Any]:
    if inspect.iscoroutinefunction(func):
        async def async_wrapper(*args: Any, **kwds: Any) -> Any:
            container = get_container()
            params_to_inject = _params_to_inject(injected_params, kwds)
            deps: dict[str, Any] = {n: await container.provide(t, n) for n, t in params_to_inject}
            return await func(*args, **{**deps, **kwds})
        return async_wrapper
    else:
        func = cast(Callable[..., Any], func)
        def sync_wrapper(*args: Any, **kwds: Any) -> Any:
            container = get_container()
            params_to_inject = _params_to_inject(injected_params, kwds)
            deps: dict[str, Any] = {n: container.get(t, n) for n, t in params_to_inject}
            return func(*args, **{**deps, **kwds})
        return sync_wrapper


def _make_decorator(get_container: ContainerResolver) -> InjectDecoratorProtocol:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        injected_params = get_injected_params(func)
        wrapper = _make_wrapper(func, get_container, injected_params)
        update_wrapper(wrapper, func)
        remove_params_from_signature(wrapper, injected_params)
        return wrapper

    return decorator