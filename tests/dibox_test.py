# pyright: reportUnknownLambdaType=false
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from attrs import define

from dibox import DIBox
from dibox.factory_box import FactoryFunc


@define
class Bar:
    s: str = ""

class BarDerived(Bar):
    def do_stuff(self):
        ...

class Foo:
    def __init__(self, bar: Bar):
        self.bar = bar


class TestDIBox:
    async def test_provide_raises_exception_if_dependencies_cannot_be_resolved(self):
        box = DIBox()
        class MandatoryBar:
            def __init__(self, s: Any): ...
        with pytest.raises(TypeError):
            await box.provide(MandatoryBar)

    @pytest.mark.parametrize(
        ("type_request", "arg_name"),
        [
            (Bar, None),
            (Bar, "arg"),
            (Bar | Foo, None)
        ])
    async def test_provide_returns_same_instance_on_second_call(self, type_request: type[Any], arg_name: str | None):
        box = DIBox()
        def bar_factory() -> Bar:
            return Bar(s="test")
        box.bind(Bar, factory=bar_factory)

        bar_instance1 = await box.provide(type_request, arg_name)
        bar_instance2 = await box.provide(type_request, arg_name)

        assert bar_instance1 is bar_instance2

    async def test_provide_bound_implementation(self):
        box = DIBox()
        box.bind(Bar, BarDerived, s="test")
        bar_instance = await box.provide(Bar)
        assert isinstance(bar_instance, BarDerived)
        assert bar_instance.s == "test"

    async def test_provide_bound_instance(self):
        box = DIBox()
        box.bind(Bar, instance=BarDerived(s="bound"))
        bar_instance = await box.provide(Bar)
        assert isinstance(bar_instance, Bar)
        assert bar_instance.s == "bound"

    async def test_provide_bind_to_factory(self):
        async def bar_factory() -> Bar:
            return Bar(s="async factory")
        box = DIBox()
        box.bind(Bar, factory=bar_factory)
        bar_instance = await box.provide(Bar)
        assert isinstance(bar_instance, Bar)
        assert bar_instance.s == "async factory"

    @pytest.fixture(params=("no-annotation", "typed", "generic"))
    def bar_factory(self, request: pytest.FixtureRequest) -> FactoryFunc[Bar]:
        def no_annotation(t): # type: ignore
            return BarDerived("bar")

        def with_type(t: type):
            return BarDerived("bar")

        def with_generic(t: type[Bar]):
            return BarDerived("bar")

        factories: dict[str, FactoryFunc[Bar]] = {
            "no-annotation": no_annotation,
            "typed": with_type,
            "generic": with_generic,
        }
        return factories[request.param]

    async def test_provide_bind_by_predicate_to_factory_with_type_arg(self, bar_factory: FactoryFunc[Bar]):
        box = DIBox()
        def bar_matcher(t: type):
            return issubclass(t, Bar)
        box.bind(bar_matcher, factory=bar_factory)

        bar_instance = await box.provide(BarDerived)

        assert isinstance(bar_instance, BarDerived)
        assert bar_instance.s == "bar"

    async def test_bind_async_factory_with_named_subdependencies(self):
        box = DIBox()
        async def foo_factory(special: Bar) -> Foo:
            return Foo(special)
        box.bind(Bar, BarDerived)
        box.bind(Bar, "special", lambda: Bar(s="special"))
        box.bind(Foo, foo_factory)

        foo_instance = await box.provide(Foo)
        usual_bar_instance = await box.provide(Bar)

        assert isinstance(foo_instance, Foo)
        assert isinstance(foo_instance.bar, Bar)
        assert foo_instance.bar.s == "special"
        assert isinstance(usual_bar_instance, BarDerived)
        assert usual_bar_instance is not foo_instance.bar

    async def test_provide_bind_async_factory_with_subdependencies(self):
        box = DIBox()
        async def foo_factory(special: Bar) -> Foo:
            return Foo(special)
        box.bind(Bar, instance=Bar(s="Yay"))
        box.bind(Foo, foo_factory)

        foo_instance = await box.provide(Foo) # Bar should be instantiated automatically and injected into Foo
        usual_bar_instance = await box.provide(Bar)

        assert isinstance(foo_instance, Foo)
        assert isinstance(foo_instance.bar, Bar)
        assert foo_instance.bar.s == "Yay"
        assert usual_bar_instance is foo_instance.bar

    async def test_provide_injects_previously_provided_dependencies(self):
        box = DIBox()
        bar_instance = await box.provide(Bar)  # bar = Bar()
        foo_instance = await box.provide(Foo)  # Foo(bar)
        assert isinstance(foo_instance, Foo)
        assert foo_instance.bar is bar_instance

    async def test_context_management(self):
        class FakeContextManager:
            def __init__(self):
                self.__enter__ = MagicMock(side_effect=lambda: calls.append("enter"))
                self.__exit__ = MagicMock(side_effect=lambda *args: calls.append("exit"))

        class FakeAsyncContextManager:
            def __init__(self):
                self.__aenter__ = AsyncMock(side_effect=lambda: calls.append("aenter"))
                self.__aexit__ = AsyncMock(side_effect=lambda *args: calls.append("aexit"))

        class FakeStartCloseLifecycleManager:
            def __init__(self):
                self.start = AsyncMock(side_effect=lambda: calls.append("start"))
                self.close = AsyncMock(side_effect=lambda: calls.append("close"))

        calls: list[str] = []
        async with DIBox() as box:
            instance1 = await box.provide(FakeContextManager)
            instance2 = await box.provide(FakeAsyncContextManager)
            instance3 = await box.provide(FakeStartCloseLifecycleManager)

        instance1.__enter__.assert_called_once()
        instance1.__exit__.assert_called_once()
        instance2.__aexit__.assert_awaited_once()
        instance2.__aenter__.assert_awaited_once()
        instance3.start.assert_awaited_once()
        instance3.close.assert_awaited_once()
        assert calls == [
            "enter", "aenter", "start",
            "close", "aexit", "exit"  # should be called in reverse to the order of creation
        ]

    async def test_get_returns_previously_provided_object(self):
        box = DIBox()
        foo_provided = await box.provide(Foo)
        foo_resolved = box.get(Foo)
        assert foo_resolved is foo_provided

    def test_get_raises_if_object_was_not_provided(self):
        box = DIBox()
        with pytest.raises(KeyError):
            box.get(Foo)
