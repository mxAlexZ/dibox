import inspect

import pytest

from dibox import ArgumentStrategy, DIBox, Injected, Injector, NotInjected


class Foo:
    def __init__(self, s: str):
        self.s: str = s


@pytest.fixture
async def dibox():
    async with DIBox() as box:
        box.bind(Foo, Foo(s="test"))
        await box.provide(Foo)  # pre-resolve to allow sync functions
        yield box


decorator_styles = ["@inject", "@inject()", "@injector.inject", "@injector.inject()"]

def _make_decorated(injector: Injector, decorator_style: str = "@injector.inject"):
    @injector
    def func_call(a: int, b: Injected[Foo]):
        return a, b

    @injector()
    def func_call_parenthesis(a: int, b: Injected[Foo]):
        return a, b

    @injector.inject
    def func_inject(a: int, b: Injected[Foo]):
        return a, b

    @injector.inject()
    def func_inject_parenthesis(a: int, b: Injected[Foo]):
        return a, b

    func_by_name = {
        "@inject": func_call,
        "@inject()": func_call_parenthesis,
        "@injector.inject": func_inject,
        "@injector.inject()": func_inject_parenthesis,
    }
    return func_by_name[decorator_style]


class TestInjector:

    @pytest.mark.parametrize("decorator_style", decorator_styles)
    async def test_decorator_styles(self, decorator_style: str, dibox: DIBox):
        injector = Injector(dibox)
        wrapped_func = _make_decorated(injector, decorator_style)

        res_a, res_b = wrapped_func(10)

        assert res_a == 10
        assert res_b.s == "test"
        assert set(inspect.signature(wrapped_func).parameters.keys()) == {"a"}


    async def test_optout_strategy(self, dibox: DIBox):
        injector = Injector(dibox, ArgumentStrategy.OPT_OUT)

        @injector.inject
        def func(a: NotInjected[int], b: Foo):
            return a, b

        res_a, res_b = func(10)

        assert res_a == 10
        assert res_b.s == "test"
        assert set(inspect.signature(func).parameters.keys()) == {"a"}


    async def test_override_injected_arg(self, dibox: DIBox):
        injector = Injector(dibox)
        func = _make_decorated(injector)

        res_a, res_b = func(10, b=Foo(s="override"))

        assert res_a == 10
        assert res_b.s == "override"


    async def test_async_consumer(self, dibox: DIBox):
        injector = Injector(dibox)

        @injector.inject
        async def func(a: int, b: Injected[Foo]):
            return a, b

        res_a, res_b = await func(10)

        assert res_a == 10
        assert res_b.s == "test"
