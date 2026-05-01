import re
from contextlib import AbstractContextManager, asynccontextmanager
from typing import Any, AsyncGenerator, AsyncIterator, cast, no_type_check
from unittest import mock
from unittest.mock import MagicMock

import pytest
from attrs import define

from dibox import BindingBox, DIBox, Injected, ResolutionError, ResolutionMode
from dibox.binding_box import FactoryFunc
from dibox.dimap import ANY_ARG, ANY_TYPE, WildArgName, WildType


@define
class Bar:
    s: str = ""

class BarDerived(Bar):
    def do_stuff(self):
        ...

class Foo:
    def __init__(self, bar: Bar):
        self.bar = bar


@pytest.fixture(params=["permissive", "strict", "semi-strict"])
def resolution_mode(request: pytest.FixtureRequest) -> ResolutionMode:
    return cast(ResolutionMode, request.param)


class DIBoxProvideTest:
    async def test_bound_subclass_is_instantiated_as_implementation(self, resolution_mode: ResolutionMode):
        box = DIBox(mode=resolution_mode)
        box.bind(Bar, BarDerived, s="test")
        bar_instance = await box.provide(Bar)
        assert isinstance(bar_instance, BarDerived)
        assert bar_instance.s == "test"

    async def test_bound_instance_is_returned_as_is(self, resolution_mode: ResolutionMode):
        box = DIBox(mode=resolution_mode)
        box.bind(Bar, instance=BarDerived(s="bound"))
        bar_instance = await box.provide(Bar)
        assert isinstance(bar_instance, BarDerived)
        assert bar_instance.s == "bound"

    async def test_already_provided_instance_is_injected_into_new_type(self, resolution_mode: ResolutionMode):
        box = DIBox(mode=resolution_mode)
        box.bind_many(Bar, Foo)
        bar_instance = await box.provide(Bar)  # bar = Bar()
        foo_instance = await box.provide(Foo)  # Foo(bar)
        assert isinstance(foo_instance, Foo)
        assert foo_instance.bar is bar_instance

    @pytest.mark.parametrize(
        ("type_request", "arg_name"),
        [
            (Bar, ANY_ARG),
            (Bar, "arg"),
            (Bar | Foo, ANY_ARG),
        ],
    )
    async def test_provided_instance_is_reused_on_subsequent_provide(
        self,
        resolution_mode: ResolutionMode,
        type_request: WildType[Any],
        arg_name: WildArgName,
    ):
        box = DIBox(mode=resolution_mode)
        box.bind(Bar, factory=lambda: Bar(s="test"))

        bar_instance1 = await box.provide(type_request, arg_name)
        bar_instance2 = await box.provide(type_request, arg_name)

        assert bar_instance1 is bar_instance2

    async def test_unregistered_concrete_type_is_auto_bound(self):
        box = DIBox()
        bar = await box.provide(Bar)
        assert isinstance(bar, Bar)

    async def test_unregistered_concrete_type_with_deps_is_auto_bound(self):
        box = DIBox()
        foo = await box.provide(Foo)
        assert isinstance(foo, Foo)
        assert isinstance(foo.bar, Bar)

    async def test_unresolvable_constructor_arg_raises_on_provide(self):
        box = DIBox()

        class MandatoryBar:
            def __init__(self, s: Any): ...

        with pytest.raises(TypeError):
            await box.provide(MandatoryBar)

    @pytest.mark.parametrize(
        ("requested_type", "name"),
        [
            ("I am a string, not a type", ANY_ARG),
            (Foo | Bar, "arg"),
            (ANY_TYPE, "arg"),
        ],
    )
    async def test_non_concrete_type_raises_value_error(self, requested_type: Any, name: WildArgName):
        box = DIBox()
        with pytest.raises(ResolutionError, match="not a concrete class"):
            await box.provide(requested_type, name)

    @pytest.mark.parametrize("resolution_mode", ["strict", "semi-strict"])
    async def test_strict_modes_unregistered_type_raises_resolution_error(self, resolution_mode: ResolutionMode):
        box = DIBox(mode=resolution_mode)
        with pytest.raises(ResolutionError, match="no binding found"):
            await box.provide(Bar)

    async def test_strict_mode_unbound_transitive_dependency_raises_resolution_error(self):
        box = DIBox(mode="strict")
        box.bind(Foo)  # Foo depends on Bar, which is not bound
        with pytest.raises(ResolutionError, match="no binding found"):
            await box.provide(Foo)

    async def test_semi_strict_mode_provides_unbound_transitive_dependency(self):
        box = DIBox(mode="semi-strict")
        box.bind(Foo)  # Foo depends on Bar, which is not bound
        foo = await box.provide(Foo)
        assert isinstance(foo, Foo)
        assert isinstance(foo.bar, Bar)

    async def test_resolution_stack_included_in_exception(self):
        class A:
            def __init__(self, foo: Foo, value: int): ...

        class B:
            def __init__(self, a: A): ...

        box = DIBox()

        with pytest.raises(ResolutionError, match="not a concrete class") as exc_info:
            await box.provide(B)
        error = exc_info.value
        message = str(error)
        assert re.search(r"(value: int).*(a: .*A).*(B)", message, re.DOTALL)
        assert "Foo" not in message
        assert error.resolution_stack == [(B, ANY_ARG), (A, "a"), (int, "value")]

    async def test_log_message_includes_matched_type_and_arg(self):
        box = DIBox()
        box.bind(Bar, BarDerived, s="test")
        with (
            mock.patch("dibox.dibox.logger.debug") as logger_mock,
            mock.patch("dibox.dibox.logger.isEnabledFor", return_value=True),
        ):
            await box.provide(Foo)

        assert logger_mock.call_count == 2

        debug_args = [c.args[1:] for c in logger_mock.call_args_list]
        assert debug_args[0][0] == "Foo"
        assert debug_args[1][0] == "bar: Bar"
        assert "Foo" in debug_args[1][1]


class DIBoxGetTest:
    async def test_get_returns_instance_created_by_provide(self, resolution_mode: ResolutionMode):
        box = DIBox(mode=resolution_mode)
        box.bind_many(Bar, Foo)
        foo_provided = await box.provide(Foo)
        foo_resolved = box.get(Foo)
        assert foo_resolved is foo_provided

    def test_get_raises_for_type_never_provided(self):
        box = DIBox()
        with pytest.raises(KeyError):
            box.get(Foo)


class DIBoxInjectTest:
    async def test_inject_decorator_supplies_bound_instance_to_annotated_param(self, resolution_mode: ResolutionMode):
        box = DIBox(mode=resolution_mode)
        box.bind(Bar, BarDerived(s="injected"))

        @box.inject
        async def func(bar: Injected[Bar]) -> str:
            return bar.s

        result = await func()
        assert result == "injected"


class DIBoxFactoriesTest:
    async def test_async_factory_result_used_as_instance(self, resolution_mode: ResolutionMode):
        async def bar_factory() -> Bar:
            return Bar(s="async factory")

        box = DIBox(mode=resolution_mode)
        box.bind(Bar, factory=bar_factory)
        bar_instance = await box.provide(Bar)
        assert isinstance(bar_instance, Bar)
        assert bar_instance.s == "async factory"

    async def test_factory_dependencies_are_auto_provided_and_injected(self, resolution_mode: ResolutionMode):
        box = DIBox(mode=resolution_mode)

        async def foo_factory(bar: Bar) -> Foo:
            return Foo(bar)

        box.bind(Bar, instance=Bar(s="Yay"))
        box.bind(Foo, foo_factory)

        foo_instance = await box.provide(Foo)  # Bar should be instantiated automatically and injected into Foo
        usual_bar_instance = await box.provide(Bar)

        assert isinstance(foo_instance, Foo)
        assert isinstance(foo_instance.bar, Bar)
        assert foo_instance.bar.s == "Yay"
        assert usual_bar_instance is foo_instance.bar

    async def test_named_binding_is_injected_into_matching_factory_parameter(self, resolution_mode: ResolutionMode):
        box = DIBox(mode=resolution_mode)

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
    async def test_factory_receives_matched_type_when_bound_by_predicate(
        self, resolution_mode: ResolutionMode, factory_style: str
    ):
        box = DIBox(mode=resolution_mode)
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

        with pytest.raises(ValueError, match="Test exception"):  # noqa: PT012 - `pytest.raises()` block should contain a single simple statement
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


class DIBoxModulesTest:
    async def test_type_bound_in_module_is_provided(self):
        module = BindingBox()
        module.bind(Bar, instance=Bar(s="from module"))
        box = DIBox()
        box.add_bindings(module)

        bar = await box.provide(Bar)

        assert bar.s == "from module"

    async def test_last_added_module_wins_for_same_type(self):
        m1 = BindingBox()
        m1.bind(Bar, instance=Bar(s="first"))
        m2 = BindingBox()
        m2.bind(Bar, instance=Bar(s="last"))
        box = DIBox()
        box.add_bindings(m1)
        box.add_bindings(m2)

        bar = await box.provide(Bar)

        assert bar.s == "last"

    async def test_container_own_binding_takes_precedence_over_modules(self):
        m1 = BindingBox()
        m1.bind(Bar, instance=Bar(s="module1"))
        m2 = BindingBox()
        m2.bind(Bar, instance=Bar(s="module2"))
        box = DIBox()
        box.add_bindings(m1)
        box.add_bindings(m2)
        box.bind(Bar, instance=Bar(s="container"))

        bar = await box.provide(Bar)

        assert bar.s == "container"

    async def test_cross_module_dependencies_are_wired(self):
        m1 = BindingBox()
        m1.bind(Bar, instance=Bar(s="from m1"))
        m2 = BindingBox()
        m2.bind(Foo, Foo)
        box = DIBox()
        box.add_bindings(m1)
        box.add_bindings(m2)

        foo = await box.provide(Foo)

        assert isinstance(foo, Foo)
        assert foo.bar.s == "from m1"


class DIBoxContextTest:
    async def test_from_context_returns_active_box_inside_async_with(self):
        box = DIBox()
        async with box:
            assert DIBox.from_context() is box

    def test_from_context_raises_when_no_box_is_active(self):
        with pytest.raises(RuntimeError, match="No active container"):
            DIBox.from_context()

    async def test_from_context_raises_after_box_exits(self):
        box = DIBox()
        async with box:
            pass
        with pytest.raises(RuntimeError, match="No active container"):
            DIBox.from_context()

    async def test_nested_box_becomes_active_context_on_enter(self):
        outer = DIBox()
        inner = DIBox()
        async with outer:
            async with inner:
                assert DIBox.from_context() is inner

    async def test_outer_box_is_restored_after_inner_exits(self):
        outer = DIBox()
        inner = DIBox()
        async with outer:
            async with inner:
                pass
            assert DIBox.from_context() is outer
