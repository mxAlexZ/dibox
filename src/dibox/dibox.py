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
    """A dependency injection container.

    `DIBox` is responsible for creating and managing the lifecycle of objects
    (called "services" or "dependencies"). It can automatically resolve and
    inject dependencies for requested types.

    It works as an async context manager, allowing for proper cleanup of
    resources.

    Usage example:
    ```python
    box = DIBox()
    # Bind a base class to a specific implementation
    box.bind(Service, ServiceImpl)
    # Dynamic binding: create any requested *Config class using a custom loader
    box.bind(lambda t: t.__name__.endswith("Config"), lambda config_type: load_config(config_type))

    async with box:
        # Concrete classes don't need special binding and can be resolved automatically,
        # including its dependencies.
        concrete_service = await box.provide(MyService)
        # Get an instance of Service, DIBox will create ServiceImpl and any of its dependencies.
        service = await box.provide(Service)
        # Provide DbConfig, which matches the predicate and will be created by the factory function.
        db_config = await box.provide(DbConfig)
    """
    def __init__(self):
        self.instances = _InstanceBox()
        self.factories = _FactoryBox()
        self._startup_func: None | Callable[[], Awaitable[None]] = None

    def bind(self, type_selector: TypeSelector[_T], to: _T | FactoryFunc[_T], name: ArgNameRequest = None, **kwargs):
        """
        Binds a type or a predicate to a specific implementation or instance.

        Args:
            type_selector: The type to bind or a predicate
                (a function that takes a type and returns a boolean).
            to: The implementation to use. Can be a class, a factory function,
                or a specific instance.
            name: An optional argument name for the binding.
            **kwargs: Additional keyword arguments to pass to the factory
                function when creating an instance.
        """
        if callable(to):
            self.factories.bind(type_selector, cast(FactoryFunc[_T], to), argname=name, **kwargs)  # bind to a factory
        elif callable(type_selector) and not inspect.isclass(type_selector):
            self.factories.bind(type_selector, lambda: to, argname=name)    # a predicate selector bound to an instance
        elif kwargs:
            raise ValueError("kwargs are only allowed when binding to a callable")
        else:
            self.instances.register_instance(type_selector, name, to)

    async def provide(self, requested_type: TypeRequest[_T], name: ArgNameRequest = None) -> _T:
        """Provides an instance of the requested type.

        If an instance is already created, it will be returned. Otherwise, a new
        instance will be created, with all its dependencies resolved and
        injected automatically. In most cases, you would not need to call this
        method directly, as it is used internally by the `inject` decorator.

        Args:
            requested_type: The type of the instance to provide.
            name: The optional argument name.

        Returns:
            An instance of the requested type.
        """
        try:
            instance = self.resolve(requested_type, name)
        except KeyError:
            instance = await self._create_instance(requested_type, name)
        return instance

    def resolve(self, requested_type: TypeRequest[_T], name: ArgNameRequest = None ) -> _T:
        """Resolves an already created instance of the requested type.

        This is a synchronous method that does not create new instances.

        Args:
            requested_type: The type of the instance to resolve.
            name: The optional argument name.

        Returns:
            The existing instance of the requested type.

        Raises:
            KeyError: If no instance of the requested type is found.
        """
        instance = self.instances.get_instance(requested_type, name)
        if instance is None:
            raise KeyError(f"Instance of {requested_type} is not found")
        return instance

    async def close(self):
        """Closes the container and cleans up all created instances.

        This method is called automatically when exiting an `async with` block.
        """
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
