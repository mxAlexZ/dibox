from typing import Callable, TypeVar

from .dibox import DIBox
from .injector import Injector

_R = TypeVar("_R")

global_dibox = DIBox()
_global_injector = Injector(global_dibox)

def inject(func: Callable[..., _R]) -> Callable[..., _R]:
    """
    Decorator for injecting dependencies into a function from a DI container.

    This decorator should only be used at application entry points; for example,
    at REST endpoint definitions like AWS lambda handlers or FastAPI routes.

    By default (in `ArgumentStrategy.OPT_IN`), it injects dependencies only for
    parameters annotated with `Injected`. The decorated function's signature is
    modified to remove the injected parameters, so they don't need to be passed
    when calling it. However, they can still be passed as keyword arguments to
    override the injection.

    Usage:

    ```python
    @inject
    def consumer(foo: Injected[Foo]): ...
    ```

    For non-global containers, use `box.inject` or `Injector(box).inject`.
    """
    return _global_injector.inject(func)
