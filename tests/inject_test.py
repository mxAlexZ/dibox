import inspect

import pytest_asyncio
from attrs import define

from dibox import DIBox, Injected, NotInjected, global_dibox, inject, inject_all


@define
class _Foo:
    s: str = ""

_box = DIBox()

@inject(_box)
def _consumer_func_sync(a: int,  foo: Injected[_Foo]):
    return a, foo

@inject(_box)
async def _async_consumer_func(a: int,  foo: Injected[_Foo]):
    return a, foo

@inject()
async def _async_consumer_func_global_box(a: int,  foo: Injected[_Foo]):
    return a, foo

@inject_all()
async def _hungry_consumer_func(a: NotInjected[int], foo: _Foo):
    return a, foo

class TestInjectDecorator:
    @pytest_asyncio.fixture(autouse=True)
    async def clear_boxes(self):
        async with _box, global_dibox:
            yield

    async def test_sync_consumer_func_resolves_registered_objects(self):
        foo = await _box.provide(_Foo)
        res_a, res_foo = _consumer_func_sync(10)  # type: ignore
        assert res_a == 10
        assert res_foo is foo

    async def test_async_consumer_func_provides_dependencies(self):
        _box.bind(_Foo, lambda: _Foo(s="test"))
        res_a, res_foo = await _async_consumer_func(10)  # type: ignore
        assert res_a == 10
        assert res_foo.s == "test"

    async def test_async_consumer_func_global_box(self):
        res_a, res_foo = await _async_consumer_func_global_box(10)  # type: ignore
        assert res_a == 10
        assert isinstance(res_foo, _Foo)

    async def test_annotated_args_override(self):
        foo = _Foo()
        res_a, res_foo = _consumer_func_sync(a=10, foo=foo)
        assert res_a == 10
        assert res_foo is foo

    def test_changes_signature(self):
        params = list(inspect.signature(_consumer_func_sync).parameters.keys())
        assert params == ["a"]

    async def test_inject_all(self):
        res_a, res_foo = await _hungry_consumer_func(10)  # type: ignore
        assert res_a == 10
        assert isinstance(res_foo, _Foo)