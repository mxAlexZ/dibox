import inspect
from typing import Awaitable, Callable

import pytest

from dibox import DIBox, Injected, global_dibox, inject
from dibox.annotations import NotInjected
from dibox.injector import ArgumentStrategy


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
    "@inject(box)",
    "@inject(box, ArgumentStrategy.OPT_IN)",
    "@inject",
    "@inject()",
    "@inject(box, ArgumentStrategy.OPT_OUT)"
]

def _make_decorated(box: DIBox, decorator_style: str) -> WrappedFunc:
    @inject(box)
    async def func_inject_box(a: int, foo: Injected[Foo]):
        return a, foo
    @inject(box, ArgumentStrategy.OPT_IN)
    async def func_inject_box_optin(a: int, foo: Injected[Foo]):
        return a, foo
    @inject
    async def func_inject(a: int, foo: Injected[Foo]):
        return a, foo
    @inject()
    async def func_inject_parenthesis(a: int, foo: Injected[Foo]):
        return a, foo
    @inject(box, ArgumentStrategy.OPT_OUT)
    async def func_inject_box_optout(a: NotInjected[int], foo: Foo):
        return a, foo
    func_by_name: dict[str, WrappedFunc] = {
        "@inject(box)": func_inject_box,
        "@inject(box, ArgumentStrategy.OPT_IN)": func_inject_box_optin,
        "@inject": func_inject,
        "@inject()": func_inject_parenthesis,
        "@inject(box, ArgumentStrategy.OPT_OUT)": func_inject_box_optout,
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
