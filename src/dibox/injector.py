import inspect
from enum import StrEnum
from functools import update_wrapper
from typing import Any, Awaitable, Callable, Protocol, TypeVar, cast, overload

from .annotations import get_injected_params, remove_params_from_signature
from .container_protocol import ContainerProtocol

_R = TypeVar("_R")

MaybeAwaitableCallable = Callable[..., _R] | Callable[..., Awaitable[_R]]


class InjectDecoratorProtocol(Protocol):
    def __call__(self, func: Callable[..., _R]) -> Callable[..., _R]: ...


class ArgumentStrategy(StrEnum):
    """
    Specifies the mode of dependency injection for the inject decorator:
    whether all parameters with type hints should be considered for injection,
    or only those explicitly marked.
    """
    OPT_OUT = "opt_out"
    OPT_IN = "opt_in"


class SignatureModification(StrEnum):
    """
    Specifies how the inject decorator modifies the decorated function's signature:
    whether to set injected parameters as optional or to remove them from the signature.
    This is not yet implemented! Keeping it here for future consideration.
    """
    REMOVE_INJECTED = "remove_injected"
    KEEP_ALL = "keep_all"


class Injector:
    def __init__(self, container: ContainerProtocol, argument_strategy: ArgumentStrategy = ArgumentStrategy.OPT_IN):
        # also possible configuration is implicit/explicit wiring, caching, custom inject marker/function,
        # signature modification, etc.
        # note: when we add 'resolver' option, we won't know the container at the this time.
        self._decorator = make_decorator(container, argument_strategy)

    @overload
    def __call__(self, func: Callable[..., _R]) -> Callable[..., _R]: ...
    @overload
    def __call__(self) -> InjectDecoratorProtocol: ...
    def __call__(self, func: Callable[..., _R] | None = None):
        if func is not None:
            return self._decorator(func)
        return self._decorator

    @overload
    def inject(self, func: Callable[..., _R]) -> Callable[..., _R]: ...
    @overload
    def inject(self) -> InjectDecoratorProtocol: ...
    def inject(self, func: Callable[..., _R] | None = None):
        if func is not None:
            return self._decorator(func)
        return self._decorator


def _params_to_inject(injected_params: dict[str, type], kwds: dict[str, Any]):
    for name, t in injected_params.items():
        if name not in kwds:
            yield name, t

def _make_wrapper(
    func: MaybeAwaitableCallable[_R],
    container: ContainerProtocol,
    injected_params: dict[str, type],
) -> MaybeAwaitableCallable[_R]:
    if inspect.iscoroutinefunction(func):
        async def async_wrapper(*args: Any, **kwds: Any) -> _R:
            params_to_inject = _params_to_inject(injected_params, kwds)
            deps: dict[str, Any] = {n: await container.provide(t, n) for n, t in params_to_inject}
            return await func(*args, **{**deps, **kwds})
        return async_wrapper
    else:
        func = cast(Callable[..., _R], func)
        def sync_wrapper(*args: Any, **kwds: Any) -> _R:
            params_to_inject = _params_to_inject(injected_params, kwds)
            deps: dict[str, Any] = {n: container.get(t, n) for n, t in params_to_inject}
            return func(*args, **{**deps, **kwds})
        return sync_wrapper


def make_decorator(
    container: ContainerProtocol,
    argument_strategy: ArgumentStrategy,
) -> InjectDecoratorProtocol:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        injected_params = get_injected_params(func, argument_strategy == ArgumentStrategy.OPT_OUT)
        wrapper = _make_wrapper(func, container, injected_params)
        update_wrapper(wrapper, func)
        remove_params_from_signature(wrapper, injected_params)
        return wrapper
    return decorator
