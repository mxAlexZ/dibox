import inspect
from functools import partial

import pytest

from dibox import BindingRecord


class _Foo:
    def __init__(self, tag: str = "test") -> None:
        self.tag = tag


class BindingRecordTest:
    def test_constructor_uses_explicit_name_when_provided(self):
        record = BindingRecord(_Foo, name="custom-name")

        assert record.name == "custom-name"
        assert str(record) == "custom-name"

    def test_constructor_name_defaults_to_class_name(self):
        record = BindingRecord(_Foo)

        assert record.name == "_Foo"
        assert str(record) == "_Foo"

    def test_constructor_name_defaults_to_factory_name(self):
        def factory() -> _Foo:
            return _Foo()

        record = BindingRecord(factory)

        assert record.name == "factory"
        assert str(record) == "factory"

    def test_constructor_name_falls_back_to_string_for_callable_object(self):
        def factory(tag: str) -> _Foo:
            return _Foo(tag)
        callable_object = partial(factory, tag="value")  # partial objects don't have a __name__

        record = BindingRecord(callable_object)

        expected_name = str(callable_object) # functools.partial(<function ... at ...>, tag='value')
        assert record.name == expected_name
        assert str(record) == expected_name

    def test_signature_info_exposes_wrapped_factory_signature(self):
        def factory(a: int, b: str = "x") -> _Foo:
            return _Foo(f"{a}:{b}")

        record = BindingRecord(factory)

        assert record.signature == inspect.signature(factory)

    def _sync_factory(self, tag: str) -> _Foo:
        return _Foo(tag)

    async def _async_factory(self, tag: str) -> _Foo:
        return _Foo(tag)

    def test_call_sync_invokes_sync_factory(self):
        record = BindingRecord(self._sync_factory)

        result = record.call_sync("sync-test")

        assert isinstance(result, _Foo)
        assert result.tag == "sync-test"

    def test_call_sync_raises_if_factory_is_async(self):
        record = BindingRecord(self._async_factory)

        with pytest.raises(RuntimeError, match="synchronous calls are not supported"):
            record.call_sync()

    async def test_call_async_invokes_async_factory(self):
        record = BindingRecord(self._async_factory)

        result = await record.call_async("async-test")

        assert isinstance(result, _Foo)
        assert result.tag == "async-test"

    async def test_call_async_invokes_sync_factory(self):
        record = BindingRecord(self._sync_factory)

        result = await record.call_async("async-to-sync-test")

        assert isinstance(result, _Foo)
        assert result.tag == "async-to-sync-test"

    async def test_partial_binds_arguments_and_assigns_name(self):
        async def factory(prefix: str, value: str) -> _Foo:
            return _Foo(f"{prefix}:{value}")

        record = BindingRecord(factory)

        partially_bound = record.partial(binding_name="partially-bound", args=("prefix",))

        assert (await partially_bound.call_async("v")).tag == "prefix:v"
        assert partially_bound.name == "partially-bound"
