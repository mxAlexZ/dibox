from typing import Any, Callable, TypeVar, overload

from .dibox import DIBox
from .injector import ArgumentStrategy, InjectDecoratorProtocol, make_decorator

_R = TypeVar("_R")

global_dibox = DIBox()


@overload
def inject(container: Callable[..., _R]) -> Callable[..., _R]: ...
@overload
def inject(container: DIBox = ..., argument_strategy: ArgumentStrategy = ...) -> InjectDecoratorProtocol: ...
def inject(
    container: DIBox | Callable[..., Any] = global_dibox,
    argument_strategy: ArgumentStrategy = ArgumentStrategy.OPT_IN,
) -> InjectDecoratorProtocol | Callable[..., Any]:
    """
    Decorator for injecting dependencies into a function from a DI container.

    This decorator should only be used at application entry points; for example,
    at REST endpoint definitions like AWS lambda handlers or FastAPI routes.

    By default (in `ArgumentStrategy.OPT_IN`), it injects dependencies only for
    parameters annotated with `Injected`. The decorated function's signature is
    modified to remove the injected parameters, so they don't need to be passed
    when calling it. However, they can still be passed as keyword arguments to
    override the injection.

    Supports both bracket and no-bracket usage:

    ```python
    @inject
    def consumer(foo: Injected[Foo]): ...

    @inject(my_container)
    def consumer(foo: Injected[Foo]): ...
    ```
    """
    if not isinstance(container, DIBox):  # Called as @inject without parentheses
        wrapped_func = container # that isn't a container, but the function to wrap ;)
        return make_decorator(global_dibox, argument_strategy)(wrapped_func)
    return make_decorator(container, argument_strategy)
