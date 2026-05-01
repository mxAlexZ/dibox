import asyncio
import inspect
from typing import Any, Union
from unittest.mock import Mock

import pytest

from dibox import ANY_ARG, ANY_TYPE, BindingBox, TypeQuery, WildArgName, WildType


class _Service:
    def __init__(self, tag: str):
        self.tag = tag

class _ServiceImpl(_Service):
    def __init__(self, tag: str = "impl"):
        super().__init__(tag)

class _Foo(_Service): ...

class _Foo2(_Service):
    def __init__(self, tag: str = "_Foo2"):
        super().__init__(tag)

def _sync_factory():
    return _ServiceImpl("sync_f")

async def _async_factory():
    await asyncio.sleep(0)  # just to make it actually async
    return _ServiceImpl("async_f")

def _is_foo(t: type[Any]) -> bool:
    return "Foo" in t.__name__

def _always_true(t: type[Any]) -> bool:
    return True


_service_instance = _ServiceImpl("instance")


class BindingBoxTest:
    def _get_valid_bind_overload_case(self, box: BindingBox, test_id: str) -> tuple[TypeQuery[Any], WildArgName, str]:
        # requested_type, request_arg, expected_tag
        match test_id:
            case "type":
                box.bind(_ServiceImpl)
                return _ServiceImpl, ANY_ARG, "impl"
            case "type, impl":
                box.bind(_Service, _ServiceImpl)
                return _Service, ANY_ARG, "impl"
            case "type, sync_factory":
                box.bind(_Service, _sync_factory)
                return _Service, ANY_ARG, "sync_f"
            case "type, async_factory":
                box.bind(_Service, _async_factory)
                return _Service, ANY_ARG, "async_f"
            case "type, instance":
                box.bind(_Service, _service_instance)
                return _Service, ANY_ARG, "instance"
            case "type, arg, impl":
                box.bind(_Service, "arg", _ServiceImpl)
                return _Service, "arg", "impl"
            case "type, arg, sync_factory":
                box.bind(_Service, "arg", _sync_factory)
                return _Service, "arg", "sync_f"
            case "type, arg, async_factory":
                box.bind(_Service, "arg", _async_factory)
                return _Service, "arg", "async_f"
            case "type, arg, instance":
                box.bind(_Service, "arg", _service_instance)
                return _Service, "arg", "instance"
            case "type, target=":
                box.bind(_Service, target=_ServiceImpl)
                return _Service, ANY_ARG, "impl"
            case "type, factory=":
                box.bind(_Service, factory=_sync_factory)
                return _Service, ANY_ARG, "sync_f"
            case "type, instance=":
                box.bind(_Service, instance=_service_instance)
                return _Service, ANY_ARG, "instance"
            case "type, arg, target=":
                box.bind(_Service, "arg", target=_ServiceImpl)
                return _Service, "arg", "impl"
            case "type, arg, factory=":
                box.bind(_Service, "arg", factory=_sync_factory)
                return _Service, "arg", "sync_f"
            case "type, arg, instance=":
                box.bind(_Service, "arg", instance=_service_instance)
                return _Service, "arg", "instance"
            case "type, name=, target=":
                box.bind(_Service, name="arg", target=_service_instance)
                return _Service, "arg", "instance"
            case "type_selector=, name=":
                box.bind(type_selector=_Service, name="arg", target=_ServiceImpl)
                return _Service, "arg", "impl"
            case "name=, target=":
                box.bind(name="arg", target=_ServiceImpl)
                return ANY_TYPE, "arg", "impl"
            case "predicate, factory":
                box.bind(_is_foo, lambda: _Foo("foo"))
                return _Foo, "foo_arg", "foo"
            case _:
                pytest.fail(f"Unknown test_id: {test_id}")

    @pytest.mark.parametrize("test_id", [
        "type",
        "type, impl",
        "type, sync_factory",
        "type, async_factory",
        "type, instance",
        "type, arg, impl",
        "type, arg, sync_factory",
        "type, arg, async_factory",
        "type, arg, instance",
        "type, target=",
        "type, factory=",
        "type, instance=",
        "type, arg, target=",
        "type, arg, factory=",
        "type, arg, instance=",
        "type, name=, target=",
        "type_selector=, name=",
        "name=, target=",
        "predicate, factory",
    ])
    async def test_valid_bind_overload_registers_callable_binding(self, test_id: str):
        box = BindingBox()
        request_type, request_arg, expected_tag = self._get_valid_bind_overload_case(box, test_id)
        binding, _ = box.find_binding(request_type, request_arg)
        assert binding is not None
        assert (await binding.call_async()).tag == expected_tag

    def _make_conflicting_bind_overloads_case(self, box: BindingBox, test_id: str) -> None:
        match test_id:
            case "(predicate)":
                box.bind(_is_foo) # type: ignore
            case "(type, type_selector=...)":
                box.bind(_Service, type_selector=_Service) # type: ignore
            case "(type, name=...)":
                box.bind(_Service, name="arg") # type: ignore
            # (type, "arg") is actually "valid" - "arg" is treated as a target
            case "(type, arg, name=...)":
                box.bind(_Service, "arg", name="arg") # type: ignore
            case "(type, arg, type_selector=...)":
                box.bind(_Service, "arg", type_selector=_Service) # type: ignore
            case "(type, arg, type_selector=..., target=...)":
                box.bind(_Service, "arg", type_selector=_Service, target=_ServiceImpl) # type: ignore
            case "(type, arg, name=..., target=...)":
                box.bind(_Service, "arg", name="arg", target=_ServiceImpl) # type: ignore
            case "(type, arg, target, target=...)":
                box.bind(_Service, "arg", _ServiceImpl, target=_ServiceImpl) # type: ignore
            case "(type, arg, target, factory=...)":
                box.bind(_Service, "arg", _ServiceImpl, factory=_sync_factory) # type: ignore
            case "(type, arg, target, instance=...)":
                box.bind(_Service, "arg", _ServiceImpl, instance=_service_instance) # type: ignore
            case "(type, arg, target=..., factory=...)":
                box.bind(_Service, "arg", target=_ServiceImpl, factory=_sync_factory) # type: ignore
            case "(type, arg, target, target)":
                box.bind(_Service, "arg", _ServiceImpl, _ServiceImpl) # type: ignore
            # case ""
            case _:
                pytest.fail(f"Unknown test_id: {test_id}")

    @pytest.mark.parametrize("test_id", [
        "(predicate)",
        "(type, type_selector=...)",
        "(type, name=...)",
        "(type, arg, name=...)",
        "(type, arg, type_selector=...)",
        "(type, arg, type_selector=..., target=...)",
        "(type, arg, name=..., target=...)",
        "(type, arg, target, target=...)",
        "(type, arg, target, factory=...)",
        "(type, arg, target, instance=...)",
        "(type, arg, target=..., factory=...)",
        "(type, arg, target, target)",
    ])
    async def test_conflicting_bind_arguments_raise_type_error(self, test_id: str):
        box = BindingBox()
        with pytest.raises(TypeError):
            self._make_conflicting_bind_overloads_case(box, test_id)

    def _make_invalid_bind_argument_values_case(self, box: BindingBox, test_id: str):
        match test_id:
            case "(predicate, name=..., target=...)":
                box.bind(_always_true, name="arg", target=_ServiceImpl)
            case "(type, arg, instance=..., **)":
                box.bind(_Service, "arg", instance=_service_instance, extra_kwarg="extra")
            case "(type, arg, instance, **)":
                box.bind(_Service, "arg", _service_instance, extra_kwarg="extra")
            case _:
                pytest.fail(f"Unknown test_id: {test_id}")

    @pytest.mark.parametrize("test_id", [
        "(predicate, name=..., target=...)",
        "(type, arg, instance=..., **)",
        "(type, arg, instance, **)",
    ])
    async def test_invalid_bind_argument_values_raise_value_error(self, test_id: str):
        box = BindingBox()
        with pytest.raises(ValueError, match="."):
            self._make_invalid_bind_argument_values_case(box, test_id)

    async def test_factory_extra_args_can_be_partially_bound_at_registration(self):
        def factory(t: type, a: str, b: str):
            return t(f"{a} {b}")

        box = BindingBox()
        box.bind(_Service, factory, a="hello")

        binding, _ = box.find_binding(_Service, "arg")
        assert binding is not None
        # 'a' is already bound and 'b' needs to be provided
        tag = binding.call_sync(_ServiceImpl, b="world").tag
        assert tag == "hello world"

    @pytest.mark.parametrize(
        ("requested_type", "request_arg", "expected_matched_type", "expected_matched_arg", "expected_tag"),
        [
            (_Service, "rand_arg", _Service, ANY_ARG, "impl"),
            (_Service, "impl2_arg", _Service, "impl2_arg", "impl2"),
            (_Foo, "foo_arg", _Foo, ANY_ARG, "_Foo"),
            (_Foo2, "foo_arg", _Foo2, ANY_ARG, "_Foo2"),
            (_Service | str, "rand_arg", _Service, ANY_ARG, "impl"),
            (Union[_Service, str], "rand_arg", _Service, ANY_ARG, "impl"),
        ],
    )
    def test_find_binding_returns_correct_binding_record_and_matching_data(
        self,
        requested_type: TypeQuery[Any],
        request_arg: WildArgName,
        expected_matched_type: WildType[Any],
        expected_matched_arg: WildArgName,
        expected_tag: str,
    ):
        def _foo_factory(t: type[Any]) -> _Foo:
            return _Foo(t.__name__)

        box = BindingBox()
        box.bind(_Service, _ServiceImpl)
        box.bind(_Service, "impl2_arg", lambda: _ServiceImpl("impl2"))
        box.bind(_is_foo, _foo_factory)

        binding, (matched_type, matched_arg) = box.find_binding(requested_type, request_arg)

        assert binding is not None
        assert binding.sync_factory is not None
        try:
            tag = binding.call_sync().tag
        except TypeError:
            tag = binding.call_sync(requested_type).tag
        assert binding.signature_info == inspect.signature(binding.sync_factory)
        assert tag == expected_tag
        assert matched_type == expected_matched_type
        assert matched_arg == expected_matched_arg

    def test_find_binding_returns_none_when_no_match(self):
        box = BindingBox()
        binding, _ = box.find_binding(_ServiceImpl, "rand_arg")
        assert binding is None

    @pytest.mark.parametrize(
        ("bind_args", "bind_kwargs", "expected_tag"),
        [
            ((_Service, _ServiceImpl), {}, "impl"),
            ((_Service, _sync_factory), {}, "sync_f"),
            ((_Service, _service_instance), {}, "instance"),
        ],
    )
    def test_sync_binding_is_callable_synchronously(
        self, bind_args: tuple[Any, ...], bind_kwargs: dict[str, Any], expected_tag: str
    ):
        box = BindingBox()
        box.bind(*bind_args, **bind_kwargs)
        binding, _ = box.find_binding(_Service, ANY_ARG)
        assert binding is not None

        tag = binding.call_sync().tag

        assert tag == expected_tag

    def test_async_binding_raises_when_called_synchronously(self):
        box = BindingBox()
        box.bind(_Service, _async_factory)
        binding, _ = box.find_binding(_Service, ANY_ARG)
        assert binding is not None

        with pytest.raises(RuntimeError):
            binding.call_sync()

    async def test_async_generator_factory_is_wrapped_with_asynccontextmanager(self):
        start = Mock()
        close = Mock()
        async def async_gen_factory():
            start()
            yield _ServiceImpl("gen_f")
            close()

        box = BindingBox()
        box.bind(_Service, async_gen_factory)
        binding, _ = box.find_binding(_Service, ANY_ARG)
        assert binding is not None

        async with await binding.call_async() as service:
            assert service.tag == "gen_f"
            start.assert_called_once()
            close.assert_not_called()
        close.assert_called_once()

    async def test_generator_factory_is_wrapped_with_contextmanager(self):
        start = Mock()
        close = Mock()
        def gen_factory():
            start()
            yield _ServiceImpl("gen_f")
            close()

        box = BindingBox()
        box.bind(_Service, gen_factory)
        binding, _ = box.find_binding(_Service, ANY_ARG)
        assert binding is not None

        with binding.call_sync() as service:
            assert service.tag == "gen_f"
            start.assert_called_once()
            close.assert_not_called()
        close.assert_called_once()

    def test_bind_many_registers_all_types(self):
        box = BindingBox()
        box.bind_many(_ServiceImpl, _Foo2)
        t1 = box.find_binding(_ServiceImpl, ANY_ARG)[0]
        assert t1 is not None
        assert isinstance(t1.call_sync(), _ServiceImpl)
        t2 = box.find_binding(_Foo2, ANY_ARG)[0]
        assert t2 is not None
        assert isinstance(t2.call_sync(), _Foo2)
