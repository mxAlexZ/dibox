import inspect
import logging
from typing import Any, TypeVar, get_origin

from .dimap import ArgNameQuery, TypeQuery
from .factory_box import BindingRecord, FactoryBox
from .instance_box import InstanceBox

_T = TypeVar('_T')
logger = logging.getLogger(__name__)

class DIBox(FactoryBox):
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
        self.instances = InstanceBox()
        super().__init__()

    async def provide(self, requested_type: TypeQuery[_T], name: ArgNameQuery = None) -> _T:
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

    def resolve(self, requested_type: TypeQuery[_T], name: ArgNameQuery = None ) -> _T:
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

    async def _create_instance(self, requested_type: TypeQuery[_T], name: ArgNameQuery) -> _T:
        logger.debug("Creating instance of %s: %s...", name, requested_type)
        binding_record, (matched_type, matched_arg) = self.find_binding(requested_type, name)
        # the first argument can be used as a type of the dependency to be created
        args_override = self._bind_factory_type_argument(matched_type, binding_record)
        args = await self._provide_dependencies(binding_record, args_override)
        factory = binding_record.async_factory or binding_record.sync_factory
        # todo: branch sync/async
        assert factory is not None, "Binding record must have at least one factory"
        instance = await self.instances.create_instance(matched_type, matched_arg, factory, **args)
        logger.debug("Instance of %s: %s was created", matched_type, matched_arg)
        return instance

    async def _provide_dependencies(self, consumer: BindingRecord[Any], args_override: dict[str, Any]) -> dict[str, Any]:
        args = self._list_dependencies(consumer, args_override)
        dependencies: dict[str, Any] = {}
        for arg_name, arg_type in args:
            # In theory, we can compose dependency graph
            # and visualize it with graphviz or something
            dependencies[arg_name] = await self.provide(arg_type, arg_name)
        dependencies |= args_override
        return dependencies

    @staticmethod
    def _list_dependencies(consumer: BindingRecord[Any], args_override: dict[str, Any]) -> list[tuple[str, type]]:
        res: list[tuple[str, type]] = []
        signature = consumer.signature_info
        for parameter in signature.parameters.values():
            if (parameter.default == inspect.Parameter.empty
                and parameter.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
                and parameter.name not in args_override
                and parameter.annotation != inspect.Parameter.empty
            ):
                res.append((parameter.name, parameter.annotation))
        return res

    @staticmethod
    def _bind_factory_type_argument(type_to_create: type[Any] | None, binding_record: BindingRecord[Any]) -> dict[str, Any]:
        # the first argument can be used as a type of the dependency to be created
        res: dict[str, Any] = {}
        signature = binding_record.signature_info
        first_arg = next(iter(signature.parameters.values()), None)
        if first_arg is not None:
            arg_type = first_arg.annotation
            # no type annotation or type or type[...] => treat it as a type argument
            if arg_type == inspect.Parameter.empty or arg_type is type or get_origin(arg_type) is type:
                res[first_arg.name] = type_to_create
        return res

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args: Any):
        await self.close()
