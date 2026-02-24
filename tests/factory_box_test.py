import asyncio
import inspect
from typing import Any, Union

import pytest

from dibox.factory_box import FactoryBox


class _Service:
    def __init__(self, tag: str):
        self.tag = tag

class _ServiceImpl(_Service):
    def __init__(self, tag: str = "impl"):
        super().__init__(tag)

class _Foo(_Service): ...

class _Foo2(_Service): ...

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

class FactoryBoxTest:
    @pytest.mark.parametrize(
        ("bind_args", "bind_kwargs", "requested_type", "request_arg", "expected_tag"),
        [
            ((_Service, _ServiceImpl), {}, _Service, None, "impl"),
            ((_Service, _sync_factory), {}, _Service, None, "sync_f"),
            ((_Service, _async_factory), {}, _Service, None, "async_f"),
            ((_Service, _service_instance), {}, _Service, None, "instance"),
            ((_Service, "arg", _ServiceImpl), {}, _Service, "arg", "impl"),
            ((_Service, "arg", _sync_factory), {}, _Service, "arg", "sync_f"),
            ((_Service, "arg", _async_factory), {}, _Service, "arg", "async_f"),
            ((_Service, "arg", _service_instance), {}, _Service, "arg", "instance"),
            ((_Service,), {"target": _ServiceImpl}, _Service, None, "impl"),
            ((_Service,), {"factory": _sync_factory}, _Service, None, "sync_f"),
            ((_Service,), {"instance": _service_instance}, _Service, None, "instance"),
            ((_Service, "arg"), {"target": _ServiceImpl}, _Service, "arg", "impl"),
            ((_Service, "arg"), {"factory": _sync_factory}, _Service, "arg", "sync_f"),
            ((_Service, "arg"), {"instance": _service_instance}, _Service, "arg", "instance"),
            ((_Service,), {"argname": "arg", "target": _service_instance}, _Service, "arg", "instance"),
            ((), {"type_selector": _Service, "argname": "arg", "target": _ServiceImpl}, _Service, "arg", "impl"),
            ((), {"argname": "arg", "target": _ServiceImpl}, None, "arg", "impl"),
            ((_is_foo, lambda: _Foo("foo")), {}, _Foo, "foo_arg", "foo"),
        ],
    )
    async def test_bind_overloads(
        self,
        bind_args: tuple[Any, ...],
        bind_kwargs: dict[str, Any],
        requested_type: type[Any] | None,
        request_arg: str | None,
        expected_tag: str,
    ):
        box = FactoryBox()
        box.bind(*bind_args, **bind_kwargs)
        binding, _ = box.find_binding(requested_type, request_arg)
        tag = (await binding.call_async()).tag
        assert tag == expected_tag

    @pytest.mark.parametrize(
        ("bind_args", "bind_kwargs", "test_name"),
        [
            ((_Service,), {}, "(type)"),
            ((_Service,), {"type_selector": _Service}, "(type, type_selector=...)"),
            ((_Service,), {"argname": "arg"}, "(type, argname=...)"),
            # (_Service, "arg")  is actually "valid" - "arg" is treated as a target
            ((_Service, "arg"), {"argname": "arg"}, "(type, arg, argname=...)"),
            ((_Service, "arg"), {"type_selector": _Service}, "(type, arg, type_selector=...)"),
            ((_Service, "arg"), {"type_selector": _Service, "target": _ServiceImpl}, "(type, arg, type_selector=..., target=...)"),  # noqa: E501
            ((_Service, "arg"), {"argname": "arg", "target": _ServiceImpl}, "(type, arg, argname=..., target=...)"),
            ((_Service, "arg", _ServiceImpl), {"target": _ServiceImpl}, "(type, arg, target, target=...)"),
            ((_Service, "arg", _ServiceImpl), {"factory": _sync_factory}, "(type, arg, target, factory=...)"),
            ((_Service, "arg", _ServiceImpl), {"instance": _service_instance}, "(type, arg, target, instance=...)"),
            ((_Service, "arg"), {"target": _ServiceImpl, "factory": _sync_factory}, "(type, arg, target=..., factory=...)"),
            ((_Service, "arg", _ServiceImpl, _ServiceImpl), {}, "(type, arg, target, target)"),
        ],
    )
    async def test_bind_invalid_signatures(self, bind_args: tuple[Any, ...], bind_kwargs: dict[str, Any], test_name: str):
        box = FactoryBox()
        with pytest.raises(TypeError):
            box.bind(*bind_args, **bind_kwargs)

    @pytest.mark.parametrize(
        ("bind_args", "bind_kwargs", "test_name"),
        [
            ((_always_true,), {"argname": "arg", "target": _ServiceImpl}, "(predicate, argname=..., target=...)"),
            ((_Service, "arg"), {"instance": _service_instance, "extra_kwarg": "extra"}, "(type, arg, instance=..., **)"),
            ((_Service, "arg", _service_instance), {"extra_kwarg": "extra"}, "(type, arg, instance, **)"),
        ],
    )
    async def test_bind_invalid_values(self, bind_args: tuple[Any, ...], bind_kwargs: dict[str, Any], test_name: str):
        box = FactoryBox()
        with pytest.raises(ValueError, match="."):
            box.bind(*bind_args, **bind_kwargs)

    async def test_bind_factory_with_additional_args(self):
        def factory(t: type, a: str, b: str):
            return t(f"{a} {b}")

        box = FactoryBox()
        box.bind(_Service, factory, a="hello")

        binding, _ = box.find_binding(_Service, "arg")
        # 'a' is already bound and 'b' needs to be provided
        tag = binding.call_sync(_ServiceImpl, b="world").tag
        assert tag == "hello world"

    @pytest.mark.parametrize(
        ("requested_type", "request_arg", "expected_matched_type", "expected_matched_arg", "expected_tag"),
        [
            (_Service, "rand_arg", _Service, None, "impl"),
            (_Service, "impl2_arg", _Service, "impl2_arg", "impl2"),
            (_Foo, "foo_arg", _Foo, None, "_Foo"),
            (_Foo2, "foo_arg", _Foo2, None, "_Foo2"),
            (_Service | str, "rand_arg", _Service, None, "impl"),
            (Union[_Service, str], "rand_arg", _Service, None, "impl"),
            # "implicit registeration", it's one of the questionable decisions made.
            (_ServiceImpl, "rand_arg", _ServiceImpl, None, "impl"),
        ],
    )
    def test_find_binding(
        self,
        requested_type: type[Any],
        request_arg: str | None,
        expected_matched_type: type | None,
        expected_matched_arg: str | None,
        expected_tag: str,
    ):
        def _foo_factory(t: type[Any]) -> _Foo:
            return _Foo(t.__name__)

        box = FactoryBox()
        box.bind(_Service, _ServiceImpl)
        box.bind(_Service, "impl2_arg", lambda: _ServiceImpl("impl2"))
        box.bind(_is_foo, _foo_factory)

        binding, (matched_type, matched_arg) = box.find_binding(requested_type, request_arg)

        assert binding.sync_factory is not None
        try:
            tag = binding.call_sync().tag
        except TypeError:
            tag = binding.call_sync(requested_type).tag
        assert binding.signature_info == inspect.signature(binding.sync_factory)
        assert tag == expected_tag
        assert matched_type == expected_matched_type
        assert matched_arg == expected_matched_arg

    @pytest.mark.parametrize(
        ("requested_type", "request_arg"),
        [
            ("I am a string, not a type", None),
            (_Foo | _Foo2, "foo_arg"),
            (None, "arg")
        ],
    )
    def test_find_binding_raises_on_invalid_type(self, requested_type: Any, request_arg: str | None):
        box = FactoryBox()
        with pytest.raises(ValueError, match="No binding found"):
            box.find_binding(requested_type, request_arg)

    @pytest.mark.parametrize(
        ("bind_args", "bind_kwargs", "expected_tag"),
        [
            ((_Service, _ServiceImpl), {}, "impl"),
            ((_Service, _sync_factory), {}, "sync_f"),
            ((_Service, _service_instance), {}, "instance"),
        ],
    )
    def test_sync_binding_record_callable_as_sync(
        self, bind_args: tuple[Any, ...], bind_kwargs: dict[str, Any], expected_tag: str
    ):
        box = FactoryBox()
        box.bind(*bind_args, **bind_kwargs)
        binding, _ = box.find_binding(_Service, None)

        tag = binding.call_sync().tag

        assert tag == expected_tag

    def test_async_binding_record_raises_if_called_as_sync(self):
        box = FactoryBox()
        box.bind(_Service, _async_factory)
        binding, _ = box.find_binding(_Service, None)

        with pytest.raises(RuntimeError):
            binding.call_sync()
