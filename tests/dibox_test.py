from contextlib import AbstractContextManager, asynccontextmanager
from typing import Any, AsyncGenerator, AsyncIterator, no_type_check
from unittest.mock import MagicMock

import pytest
from attrs import define

from dibox import DIBox, Injected
from dibox.binding_box import FactoryFunc


@define
class Bar:
    s: str = ""

class BarDerived(Bar):
    def do_stuff(self):
        ...

class Foo:
    def __init__(self, bar: Bar):
        self.bar = bar


class DIBoxTest:
    async def test_unresolvable_constructor_arg_raises_on_provide(self):
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
        ]
    )
    async def test_provided_instance_is_reused_on_subsequent_provide(self, type_request: type[Any], arg_name: str | None):
        box = DIBox()
        def bar_factory() -> Bar:
            return Bar(s="test")
        box.bind(Bar, factory=bar_factory)

        bar_instance1 = await box.provide(type_request, arg_name)
        bar_instance2 = await box.provide(type_request, arg_name)

        assert bar_instance1 is bar_instance2

    async def test_bound_subclass_is_instantiated_as_implementation(self):
        box = DIBox()
        box.bind(Bar, BarDerived, s="test")
        bar_instance = await box.provide(Bar)
        assert isinstance(bar_instance, BarDerived)
        assert bar_instance.s == "test"

    async def test_bound_instance_is_returned_as_is(self):
        box = DIBox()
        box.bind(Bar, instance=BarDerived(s="bound"))
        bar_instance = await box.provide(Bar)
        assert isinstance(bar_instance, BarDerived)
        assert bar_instance.s == "bound"

    async def test_already_provided_instance_is_injected_into_new_type(self):
        box = DIBox()
        bar_instance = await box.provide(Bar)  # bar = Bar()
        foo_instance = await box.provide(Foo)  # Foo(bar)
        assert isinstance(foo_instance, Foo)
        assert foo_instance.bar is bar_instance

    async def test_get_returns_instance_created_by_provide(self):
        box = DIBox()
        foo_provided = await box.provide(Foo)
        foo_resolved = box.get(Foo)
        assert foo_resolved is foo_provided

    def test_get_raises_for_type_never_provided(self):
        box = DIBox()
        with pytest.raises(KeyError):
            box.get(Foo)

    async def test_inject_decorator_supplies_bound_instance_to_annotated_param(self):
        box = DIBox()
        box.bind(Bar, BarDerived(s="injected"))
        @box.inject
        async def func(bar: Injected[Bar]) -> str:
            return bar.s
        result = await func()
        assert result == "injected"


class DIBoxFactoriesTest:

    async def test_async_factory_result_used_as_instance(self):
        async def bar_factory() -> Bar:
            return Bar(s="async factory")
        box = DIBox()
        box.bind(Bar, factory=bar_factory)
        bar_instance = await box.provide(Bar)
        assert isinstance(bar_instance, Bar)
        assert bar_instance.s == "async factory"


    async def test_factory_dependencies_are_auto_provided_and_injected(self):
        box = DIBox()
        async def foo_factory(bar: Bar) -> Foo:
            return Foo(bar)
        box.bind(Bar, instance=Bar(s="Yay"))
        box.bind(Foo, foo_factory)

        foo_instance = await box.provide(Foo) # Bar should be instantiated automatically and injected into Foo
        usual_bar_instance = await box.provide(Bar)

        assert isinstance(foo_instance, Foo)
        assert isinstance(foo_instance.bar, Bar)
        assert foo_instance.bar.s == "Yay"
        assert usual_bar_instance is foo_instance.bar


    async def test_named_binding_is_injected_into_matching_factory_parameter(self):
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


    def _make_factory_for_predicate(self, factory_style: str) -> FactoryFunc[Bar]:
        @no_type_check
        def no_annotation(t):
            return BarDerived(t.__name__)

        def with_type(t: type):
            return BarDerived(t.__name__)

        def with_generic(t: type[Bar]):
            return BarDerived(t.__name__)

        factories: dict[str, FactoryFunc[Bar]] = {
            "no-annotation": no_annotation,
            "typed": with_type,
            "generic": with_generic,
        }
        return factories[factory_style]

    @pytest.mark.parametrize("factory_style", ["no-annotation", "typed", "generic"])
    async def test_factory_receives_matched_type_when_bound_by_predicate(self, factory_style: str):
        box = DIBox()
        bar_factory = self._make_factory_for_predicate(factory_style)
        box.bind(lambda t: "Bar" in t.__name__, factory=bar_factory)

        bar_instance = await box.provide(BarDerived)

        assert isinstance(bar_instance, BarDerived)
        assert bar_instance.s == "BarDerived"


class DIBoxLifecycleManagementTest:

    async def test_teardown_order_is_lifo_across_provided_instances(self):
        call_records: list[str] = []
        class SyncStartCloseManager(Bar):
            def start(self):
                call_records.append("enter_1")
            def close(self):
                call_records.append("exit_1")

        @asynccontextmanager
        async def async_cm_factory() -> AsyncIterator[Bar]:
            call_records.append("enter_2")
            yield Bar()
            call_records.append("exit_2")

        async def async_yield_factory() -> AsyncGenerator[Bar, None]:
            call_records.append("enter_3")
            yield Bar()
            call_records.append("exit_3")

        box = DIBox()
        box.bind(name="manager_1", factory=SyncStartCloseManager)
        box.bind(name="manager_2", factory=async_cm_factory)
        box.bind(name="manager_3", factory=async_yield_factory)

        async with box:
            await box.provide(object, name="manager_1")
            await box.provide(MagicMock, name="manager_2")
            await box.provide(object, name="manager_3")

        assert call_records == ["enter_1", "enter_2", "enter_3", "exit_3", "exit_2", "exit_1"]

    async def test_raised_exception_forwarded_to_cm_exit(self):
        exit_mock = MagicMock(return_value=True)

        class ManagedBar(AbstractContextManager[Any], Bar):
            def __exit__(self, *args: Any):
                return exit_mock(*args)

        with pytest.raises(ValueError, match="Test exception"): # noqa: PT012 - `pytest.raises()` block should contain a single simple statement
            async with DIBox() as box:
                box.bind(Bar, ManagedBar())
                await box.provide(Bar)
                raise ValueError("Test exception")

        exit_mock.assert_called_once()
        exc_type, exc_val, _ = exit_mock.call_args[0]
        assert exc_type is ValueError
        assert str(exc_val) == "Test exception"

    async def test_dependency_cleaned_up_when_box_closed(self):
        exit_mock = MagicMock(return_value=True)
        class ManagedBar(AbstractContextManager[Any], Bar):
            def __exit__(self, *args: Any):
                return exit_mock(*args)

        box = DIBox()
        box.bind(Bar, ManagedBar())
        await box.provide(Bar)
        await box.close()

        exit_mock.assert_called_once()
