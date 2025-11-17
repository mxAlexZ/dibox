import inspect
import logging
from contextlib import AbstractAsyncContextManager
from typing import Any, Awaitable, Callable, TypeVar, cast, get_origin

from .dimap import ArgNameRequest, TypeRequest
from .factory_box import FactoryFunc, TypeSelector, _FactoryBox
from .instance_box import _InstanceBox

_T = TypeVar('_T')
logger = logging.getLogger(__name__)

class DIBox(AbstractAsyncContextManager):
    def __init__(self):
        self.instances = _InstanceBox()
        self.factories = _FactoryBox()
        self._startup_func: None | Callable[[], Awaitable[None]] = None

    def bind(self, type_selector: TypeSelector[_T], to: _T | FactoryFunc[_T], name: ArgNameRequest = None, **kwargs):
        if callable(to):
            self.factories.bind(type_selector, cast(FactoryFunc[_T], to), argname=name, **kwargs)  # bind to a factory
        elif callable(type_selector) and not inspect.isclass(type_selector):
            self.factories.bind(type_selector, lambda: to, argname=name)    # a predicate selector bound to an instance
        elif kwargs:
            raise ValueError("kwargs are only allowed when binding to a callable")
        else:
            self.instances.register_instance(type_selector, name, to)

    async def provide(self, requested_type: TypeRequest[_T], name: ArgNameRequest = None) -> _T:
        try:
            instance = self.resolve(requested_type, name)
        except KeyError:
            instance = await self._create_instance(requested_type, name)
        return instance

    def resolve(self, requested_type: TypeRequest[_T], name: ArgNameRequest = None ) -> _T:
        instance = self.instances.get_instance(requested_type, name)
        if instance is None:
            raise KeyError(f"Instance of {requested_type} is not found")
        return instance

    async def close(self):
        await self.instances.close()

    async def _create_instance(self, requested_type: TypeRequest[_T], name: ArgNameRequest) -> _T:
        logger.debug("Creating instance of %s: %s...", name, requested_type)
        factory, map_key = self.factories.get_factory(requested_type, name)
        # the first argument can be used as a type of the dependency to be created
        args_override = self._find_factory_bound_arguments(requested_type, factory)
        args = await self._provide_dependencies(factory, args_override)
        instance = await self.instances.create_instance(map_key[0], map_key[1], factory, **args)
        logger.debug("Instance of %s: %s was created", map_key[0], map_key[1])
        return instance

    async def _provide_dependencies(self, consumer: Callable, args_override: dict[str, Any]) -> dict[str, Any]:
        args = self._list_dependencies(consumer, args_override)
        dependencies: dict[str, Any] = {}
        for arg_name, arg_type in args:
            # In theory, we can compose dependency graph
            # and visualize it with graphviz or something
            dependencies[arg_name] = await self.provide(arg_type, arg_name)
        dependencies |= args_override
        return dependencies

    @staticmethod
    def _list_dependencies(consumer: Callable, args_override: dict[str, Any]) -> list[tuple[str, type]]:
        res = []
        signature = inspect.signature(consumer)
        for parameter in signature.parameters.values():
            if (parameter.default == inspect.Parameter.empty
                and parameter.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
                and parameter.name not in args_override
                and parameter.annotation != inspect.Parameter.empty
            ):
                res.append((parameter.name, parameter.annotation))
        return res

    @staticmethod
    def _find_factory_bound_arguments(parent_type, factory_func: Callable) -> dict[str, Any]:
        # the first argument can be used as a type of the dependency to be created
        res = {}
        signature = inspect.signature(factory_func)
        first_arg = next(iter(signature.parameters.values()), None)
        if first_arg is not None:
            arg_type = first_arg.annotation
            if arg_type == inspect.Parameter.empty or get_origin(arg_type) is type:
                res[first_arg.name] = parent_type
        return res

    async def __aexit__(self, *args):
        await self.close()
