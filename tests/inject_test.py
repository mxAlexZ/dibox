import inspect
from typing import Awaitable, Callable

import pytest

from dibox import DIBox, Injected, global_dibox, inject


class Foo:
    def __init__(self, s: str):
        self.s: str = s

# we have to operate on the global box here because its value is bound on the
# import time as a default argument to the inject decorator.
box = global_dibox

@pytest.fixture(autouse=True)
async def create_bindings():
    async with box:
        box.bind(Foo, Foo(s="test"))
        yield box

WrappedFunc = Callable[..., Awaitable[tuple[int, Foo]]]


decorator_styles = [
    "@inject",
]

def _make_decorated(_box: DIBox, decorator_style: str) -> WrappedFunc:
    @inject
    async def func_inject(a: int, foo: Injected[Foo]):
        return a, foo

    func_by_name: dict[str, WrappedFunc] = {
        "@inject": func_inject,
    }
    return func_by_name[decorator_style]

class TestInjectDecorator:
    @pytest.mark.parametrize("decorator_style", decorator_styles)
    async def test_inject(self, decorator_style: str):
        wrapped_func = _make_decorated(box, decorator_style)

        res_a, res_foo = await wrapped_func(10)

        assert res_a == 10
        assert res_foo.s == "test"
        assert set(inspect.signature(wrapped_func).parameters.keys()) == {"a"}

    @pytest.mark.parametrize("decorator_style", decorator_styles)
    async def test_inject_injected_argument_override(self, decorator_style: str):
        wrapped_func = _make_decorated(box, decorator_style)

        foo = Foo(s="override")
        res_a, res_foo = await wrapped_func(10, foo=foo)

        assert res_a == 10
        assert res_foo.s == "override"
        assert set(inspect.signature(wrapped_func).parameters.keys()) == {"a"}
