import inspect
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncIterator, Iterator
from unittest.mock import Mock

import pytest

from dibox.binding_box import BindingRecord, FactoryFunc
from dibox.dimap import ANY_ARG
from dibox.instance_box import InstanceBox


class Bar:
    ...


class InstanceBoxTest:
    async def test_get_returns_instance_created_by_create_instance(self):
        box = InstanceBox()
        instance = Bar()
        def factory():
            return instance
        binding = BindingRecord(None, factory, inspect.signature(factory))
        await box.create_instance(Bar, ANY_ARG, binding)
        assert box.get_instance(Bar) is instance

    async def test_index_exposes_exact_key_lookup_for_created_instances(self):
        box = InstanceBox()
        instance = Bar()

        def factory():
            return instance

        binding = BindingRecord(None, factory, inspect.signature(factory))
        await box.create_instance(Bar, ANY_ARG, binding)

        assert (Bar, ANY_ARG) in box.index
        assert box.index[(Bar, ANY_ARG)] is instance

    def test_get_returns_none_for_unknown_type(self):
        box = InstanceBox()
        assert box.get_instance(Bar) is None

    async def test_failed_startup_does_not_register_teardown_or_store_instance(self):
        close_mock = Mock()

        class BadStart:
            def start(self) -> None:
                raise RuntimeError("startup failed")
            def close(self) -> None:
                close_mock()

        box = InstanceBox()
        factory = BadStart
        binding = BindingRecord(None, factory, inspect.signature(factory))
        with pytest.raises(RuntimeError, match="startup failed"):
            await box.create_instance(BadStart, ANY_ARG, binding)
        await box.close()
        close_mock.assert_not_called()
        assert box.get_instance(BadStart) is None


    def _make_lifecycle_manager_binding(
        self, style: str, enter_event: Mock, exit_event: Mock
    ) -> BindingRecord:
        class SyncContextManager(Bar):
            def __enter__(self):
                enter_event()
                return self
            def __exit__(self, *args: Any):
                exit_event()

        class AsyncContextManager(Bar):
            async def __aenter__(self):
                enter_event()
                return self
            async def __aexit__(self, *args: Any):
                exit_event()

        class SyncStartCloseManager(Bar):
            def start(self):
                enter_event()
            def close(self):
                exit_event()

        class AsyncStartAcloseManager(Bar):
            async def start(self):
                enter_event()
            async def aclose(self):
                exit_event()

        @contextmanager
        def sync_cm_factory() -> Iterator[Bar]:
            enter_event()
            yield Bar()
            exit_event()

        @asynccontextmanager
        async def async_cm_factory() -> AsyncIterator[Bar]:
            enter_event()
            yield Bar()
            exit_event()


        factories: dict[str, FactoryFunc[Bar]] = {
            "SyncContextManager": SyncContextManager,
            "AsyncContextManager": AsyncContextManager,
            "SyncStartCloseManager": SyncStartCloseManager,
            "AsyncStartAcloseManager": AsyncStartAcloseManager,
            "@contextmanager": sync_cm_factory,
            "@asynccontextmanager": async_cm_factory,
        }
        factory = factories[style]
        return BindingRecord(None, factory, inspect.signature(factory))

    @pytest.mark.parametrize(
        "lifecycle_manager_style",
        [
            "SyncContextManager",
            "AsyncContextManager",
            "SyncStartCloseManager",
            "AsyncStartAcloseManager",
            "@contextmanager",
            "@asynccontextmanager"
        ]
    )
    async def test_startup_hook_called_on_instance_creation_and_teardown_on_box_exit(self, lifecycle_manager_style: str):
        enter_event = Mock()
        exit_event = Mock()
        box = InstanceBox()
        binding_record = self._make_lifecycle_manager_binding(lifecycle_manager_style, enter_event, exit_event)
        await box.create_instance(Bar, ANY_ARG, binding_record)
        enter_event.assert_called_once()
        exit_event.assert_not_called()
        await box.close()
        exit_event.assert_called_once()
