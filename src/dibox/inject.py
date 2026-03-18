from typing import Callable, TypeVar

from .dibox import DIBox
from .injector import Injector

_R = TypeVar("_R")

_context_injector = Injector(container_resolver=DIBox.from_context)


def inject(func: Callable[..., _R]) -> Callable[..., _R]:
    """
    Decorator for injecting dependencies into a function from the active container.

    The container is resolved from context at each call, so this decorator can be
    applied at import time — before any container is created. The active container
    is whichever `DIBox` is currently entered via `async with box:`.

    Only parameters annotated with `Injected[T]` are injected. Injected parameters
    are removed from the visible signature. They can still be passed as keyword
    arguments to override injection.

    Usage:

    ```python
    @inject
    async def handler(foo: Injected[Foo]): ...

    async with DIBox() as box:
        box.bind(Foo, Foo())
        await handler()  # foo is injected from box
    ```

    To tie injection to a specific container instead of the active context, use
    `box.inject` or `Injector(box).inject`.
    """
    return _context_injector.inject(func)
