import inspect

import pytest

from dibox import DIBox, Injected, Injector


class Foo:
    def __init__(self, s: str):
        self.s: str = s


@pytest.fixture
async def dibox():
    async with DIBox() as box:
        box.bind(Foo, Foo(s="test"))
        await box.provide(Foo)  # pre-resolve to allow sync functions
        yield box


def _make_decorated(injector: Injector, decorator_style: str = "@injector.inject"):
    @injector
    def func_call(a: int, b: Injected[Foo]):
        return a, b

    @injector.inject
    def func_inject(a: int, b: Injected[Foo]):
        return a, b

    func_by_name = {
        "@injector": func_call,
        "@injector.inject": func_inject,
    }
    return func_by_name[decorator_style]


class InjectorTest:
    @pytest.mark.parametrize("decorator_style", ["@injector", "@injector.inject"])
    async def test_injected_args_are_resolved(self, decorator_style: str, dibox: DIBox):
        injector = Injector(dibox)
        wrapped_func = _make_decorated(injector, decorator_style)

        res_a, res_b = wrapped_func(a=10)

        assert res_a == 10
        assert res_b.s == "test"
        assert set(inspect.signature(wrapped_func).parameters.keys()) == {"a"}

    async def test_injected_arg_can_be_overridden_with_kwarg(self, dibox: DIBox):
        injector = Injector(dibox)
        func = _make_decorated(injector)

        res_a, res_b = func(10, b=Foo(s="override"))

        assert res_a == 10
        assert res_b.s == "override"

    async def test_injected_args_are_resolved_for_async_function(self, dibox: DIBox):
        injector = Injector(dibox)

        @injector.inject
        async def func(a: int, b: Injected[Foo]):
            return a, b

        res_a, res_b = await func(10)

        assert res_a == 10
        assert res_b.s == "test"

    async def test_container_resolver_is_called_at_each_invocation(self):
        box1 = DIBox()
        box2 = DIBox()
        box1.bind(Foo, Foo(s="box1"))
        box2.bind(Foo, Foo(s="box2"))
        box_iter = iter([box1, box2])
        injector = Injector(container_resolver=lambda: next(box_iter))

        @injector.inject
        async def func(f: Injected[Foo]):
            return f

        assert (await func()).s == "box1"
        assert (await func()).s == "box2"
