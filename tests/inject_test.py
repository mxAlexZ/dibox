import inspect

import pytest

from dibox import DIBox, Injected, inject


class Foo:
    def __init__(self, s: str):
        self.s: str = s


@inject
async def _injected_func(a: int, foo: Injected[Foo]):
    return a, foo


class InjectDecoratorTest:
    async def test_injected_params_are_resolved_from_active_box(self):
        async with DIBox() as box:
            box.bind(Foo, Foo(s="test"))
            res_a, res_foo = await _injected_func(10)

        assert res_a == 10
        assert res_foo.s == "test"

    async def test_injected_params_removed_from_visible_signature(self):
        assert set(inspect.signature(_injected_func).parameters.keys()) == {"a"}

    async def test_caller_provided_arg_is_not_overridden_by_injection(self):
        async with DIBox() as box:
            box.bind(Foo, Foo(s="from box"))
            res_a, res_foo = await _injected_func(10, foo=Foo(s="override"))

        assert res_a == 10
        assert res_foo.s == "override"

    async def test_active_box_swap_changes_what_is_injected(self):
        async with DIBox() as box1:
            box1.bind(Foo, Foo(s="box1"))
            _, foo1 = await _injected_func(1)
            async with DIBox() as box2:
                box2.bind(Foo, Foo(s="box2"))
                _, foo2 = await _injected_func(2)
            _, foo1_again = await _injected_func(1)

        assert foo1.s == "box1"
        assert foo2.s == "box2"
        assert foo1_again.s == "box1"

    async def test_calling_without_active_box_raises(self):
        with pytest.raises(RuntimeError, match="No active container"):
            await _injected_func(10)
