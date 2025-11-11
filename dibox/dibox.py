import inspect
import logging
from contextlib import AbstractAsyncContextManager
from typing import Any, Awaitable, Callable, TypeVar, get_origin

from .factory_box import Factory, FactoryBox, TypeSelector
from .instance_box import InstanceBox

_T = TypeVar('_T')
logger = logging.getLogger(__name__)

class DIBox(AbstractAsyncContextManager):
    def __init__(self):
        self.instances = InstanceBox()
        self.factories = FactoryBox()
        self._startup_func: None | Callable[[], Awaitable[None]] = None

    def bind(self, type_selector: TypeSelector[_T], to: _T | Factory[_T], name: str | None = None, **kwargs):
        if callable(to):
            self.factories.bind(type_selector, to, argname=name, **kwargs)  # bind to a factory
        elif callable(type_selector) and not inspect.isclass(type_selector):
            self.factories.bind(type_selector, lambda: to, argname=name)    # a predicate selector bound to an instance
        elif kwargs:
            raise ValueError("kwargs are only allowed when binding to a callable")
        else:
            self.instances.register_instance(type_selector, name, to)

    async def provide(self, cls: type[_T], name: str | None = None) -> _T:
        try:
            instance = self.resolve(cls, name)
        except KeyError:
            instance = await self._create_instance(cls, name)
        return instance

    def resolve(self, dependency_type: type[_T], name: str | None = None ) -> _T:
        instance = self.instances.get_instance(dependency_type, name)
        if instance is None:
            raise KeyError(f"Instance of {dependency_type} is not found")
        return instance

    async def close(self):
        await self.instances.close()

    async def _create_instance(self, cls: type[_T], name: str | None) -> _T:
        logger.debug("Creating instance of %s: %s...", name, cls)
        factory, map_key = self.factories.get_factory(cls, name)
        # the first argument can be used as a type of the dependency to be created
        args_override = self._find_factory_bound_arguments(cls, factory)
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
    def _find_factory_bound_arguments(parent_type: type, factory_func: Callable) -> dict[str, Any]:
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
