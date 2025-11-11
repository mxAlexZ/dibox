from typing import Union
from unittest.mock import AsyncMock, MagicMock

import pytest
from attrs import define

from dibox import DIBox


class TestDIBox:
    async def test_provide_raises_exception_if_not_enough_arguments(self):
        box = DIBox()
        class MandatoryBar:
            def __init__(self, s: str): ...
        with pytest.raises(Exception):
            await box.provide(MandatoryBar)

    async def test_provide_raises_exception_if_not_class(self):
        box = DIBox()
        with pytest.raises(ValueError):
            await box.provide(int)

    async def test_provide_returns_same_instance_on_second_call(self):
        box = DIBox()
        bar_instance1 = await box.provide(Bar)
        bar_instance2 = await box.provide(Bar)
        assert bar_instance1 is bar_instance2

    async def test_bind_derived_class(self):
        box = DIBox()
        box.bind(Bar, to=BarDerived, s="test")
        bar_instance = await box.provide(Bar)
        assert isinstance(bar_instance, BarDerived)
        assert bar_instance.s == "test"

    async def test_bind_instance(self):
        box = DIBox()
        box.bind(Bar, to=BarDerived(s="bound"))
        bar_instance = await box.provide(Bar)
        assert isinstance(bar_instance, Bar)
        assert bar_instance.s == "bound"

    async def test_bind_factory(self):
        box = DIBox()
        box.bind(Bar, to=lambda: BarDerived(s="bound"))
        bar_instance = await box.provide(Bar)
        assert isinstance(bar_instance, Bar)
        assert bar_instance.s == "bound"

    async def test_bind_factory_with_type_arg(self):
        box = DIBox()
        box.bind(Bar, to=lambda t: t(s="bound"))
        bar_instance = await box.provide(Bar)
        assert isinstance(bar_instance, Bar)
        assert bar_instance.s == "bound"

    async def test_bind_by_predicate_to_instance(self):
        box = DIBox()
        box.bind(lambda t: issubclass(t, Bar), to=BarDerived(s="stuff"))
        bar_instance = await box.provide(Bar)
        assert isinstance(bar_instance, BarDerived)
        assert bar_instance.s == "stuff"

    async def test_bind_by_predicate_to_callable(self):
        box = DIBox()
        box.bind(lambda t: issubclass(t, Bar), to=lambda: BarDerived(s="stuff"))
        bar_instance = await box.provide(Bar)
        assert isinstance(bar_instance, BarDerived)
        assert bar_instance.s == "stuff"
        assert await box.provide(Bar) is bar_instance

    async def test_bind_async_factory(self):
        box = DIBox()
        async def bar_factory() -> Bar:
            return BarDerived(s="bound")
        box.bind(Bar, to=bar_factory)
        bar_instance = await box.provide(Bar)
        assert isinstance(bar_instance, Bar)
        assert bar_instance.s == "bound"

    async def test_bind_async_factory_with_subdependencies(self):
        box = DIBox()
        async def foo_factory(bar: Bar) -> Foo:
            return Foo(bar)
        box.bind(Foo, to=foo_factory)
        foo_instance = await box.provide(Foo)
        assert isinstance(foo_instance, Foo)
        assert isinstance(foo_instance.bar, Bar)
        assert await box.provide(Bar) is foo_instance.bar

    async def test_bind_async_factory_with_named_subdependencies(self):
        box = DIBox()
        async def foo_factory(special: Bar) -> Foo:
            return Foo(special)
        box.bind(Bar, BarDerived)
        box.bind(Bar, to=lambda: Bar(s="special"), name="special")
        box.bind(Foo, to=foo_factory)

        foo_instance = await box.provide(Foo)
        usual_bar_instance = await box.provide(Bar)

        assert isinstance(foo_instance, Foo)
        assert isinstance(foo_instance.bar, Bar)
        assert foo_instance.bar.s == "special"
        assert isinstance(usual_bar_instance, BarDerived)
        assert usual_bar_instance is not foo_instance.bar

    async def test_bind_async_factory_with_untyped_named_subdependencies(self):
        box = DIBox()
        async def foo_factory(special: Bar) -> Foo:
            return Foo(special)
        box.bind(Bar, BarDerived)
        box.bind(None, name="special", to=Bar(s="special"))
        box.bind(Foo, to=foo_factory)

        foo_instance = await box.provide(Foo)
        usual_bar_instance = await box.provide(Bar)

        assert isinstance(foo_instance, Foo)
        assert isinstance(foo_instance.bar, Bar)
        assert foo_instance.bar.s == "special"
        assert isinstance(usual_bar_instance, BarDerived)
        assert usual_bar_instance is not foo_instance.bar

    async def test_bind_async_factory_with_kw_args(self):
        box = DIBox()
        async def bar_factory(a: str, b: str):
            return Bar(s=f"{a}{b}")
        box.bind(Bar, to=bar_factory, a="a", b="b")
        instance = await box.provide(Bar)
        assert isinstance(instance, Bar)
        assert instance.s == "ab"
        assert await box.provide(Bar) is instance

    async def test_provide_injects_previously_provided_dependencies(self):
        box = DIBox()
        bar_instance = await box.provide(Bar)  # Bar()
        foo_instance = await box.provide(Foo)  # Foo(bar)
        assert isinstance(foo_instance, Foo)
        assert foo_instance.bar is bar_instance

    async def test_provide_automatically_creates_and_injects_subdependencies(self):
        box = DIBox()
        foo_instance = await box.provide(Foo)  # Foo(Bar()),
        assert isinstance(foo_instance, Foo)
        assert isinstance(foo_instance.bar, Bar)

    async def test_provide_union_type(self):
        box = DIBox()
        box.bind(Bar, to=BarDerived, s="test")
        bar_instance = await box.provide(int | Bar)
        assert isinstance(bar_instance, BarDerived)
        assert bar_instance.s == "test"

    async def test_provide_union(self):
        box = DIBox()
        box.bind(Bar, to=BarDerived, s="test")
        bar_instance = await box.provide(Union[int, Bar])
        assert isinstance(bar_instance, BarDerived)
        assert bar_instance.s == "test"

    async def test_context_management(self):
        calls = []
        async with DIBox() as box:
            instance1 = await box.provide(FooContext)
            instance1.__enter__.assert_called_once()
            instance1.__exit__.side_effect = lambda *args: calls.append(1)
            instance2 = await box.provide(FooAsyncContext)
            instance2.__aenter__.assert_awaited_once()
            instance2.__aexit__.side_effect = lambda *args: calls.append(2)
            instance3 = await box.provide(FooStartClose)
            instance3.start.assert_awaited_once()
            instance3.close.side_effect = lambda: calls.append(3)
        instance3.close.assert_awaited_once()
        instance2.__aexit__.assert_awaited_once()
        instance1.__exit__.assert_called_once()
        assert calls == [3, 2, 1]  # should be called in reverse to the order of creation

    async def test_resolve_returns_provided_type(self):
        box = DIBox()
        foo_provided = await box.provide(Foo)
        foo_resolved = box.resolve(Foo)
        assert foo_resolved is foo_provided

    def test_resolve_raises_if_type_not_provided(self):
        box = DIBox()
        with pytest.raises(Exception):
            box.resolve(Foo)


@define
class Bar:
    s: str = ""

class BarDerived(Bar):
    def do_stuff(self):
        ...

class Foo:
    def __init__(self, bar: Bar):
        self.bar = bar


class FooContext:
    def __init__(self):
        self.__enter__ = MagicMock()
        self.__exit__ = MagicMock()


class FooAsyncContext:
    def __init__(self):
        self.__aenter__ = AsyncMock()
        self.__aexit__ = AsyncMock()


class FooStartClose:
    def __init__(self):
        self.start = AsyncMock()
        self.close = AsyncMock()
