import inspect
import logging
from typing import Any, Awaitable, Callable, Self, TypeVar, get_origin, overload

from .dimap import ArgNameQuery, TypeQuery
from .factory_box import BindingRecord, FactoryBox
from .injector import ArgumentStrategy, Injector
from .instance_box import InstanceBox

_T = TypeVar("_T")
_R = TypeVar("_R")
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

    def __init__(self, inject_mode: ArgumentStrategy = ArgumentStrategy.OPT_IN) -> None:
        self.instances = InstanceBox()
        self.injector = Injector(self, inject_mode)
        super().__init__()

    def inject(self, func: Callable[..., _R]) -> Callable[..., _R]:
        return self.injector()(func)

    @overload
    def call(self, func: Callable[..., Awaitable[_R]], *args: Any, **kwargs: Any) -> Awaitable[_R]: ...
    @overload
    def call(self, func: Callable[..., _R], *args: Any, **kwargs: Any) -> _R: ...
    def call(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        # Todo: see the design eps - we can apply injection without markers
        # since we have access to all bindings.
        raise NotImplementedError("call() method is not implemented yet.")

    async def provide(self, requested_type: TypeQuery[_T], name: ArgNameQuery = None) -> _T:
        """Provides an instance of the requested type, with optional name-based binding.

        This is the primary method for dependency resolution. DIBox matches dependencies
        using both type and argument name, enabling named bindings where multiple instances
        of the same type can be distinguished by parameter names.

        If a matching instance already exists, it will be returned. Otherwise, DIBox will
        create a new instance, automatically resolving and injecting all its dependencies
        based on constructor type hints. Supports async factories and lifecycle management.

        TODO: _T is unknown for None type query -> We need overload with Any return type for that case.

        Args:
            requested_type: The type of the instance to provide.
            name: The argument name for named binding resolution. When provided,
                DIBox first attempts to match both type and name, falling back to
                type-only matching if no named binding exists.

        Returns:
            The existing or freshly created instance matching the type and name criteria.
        """
        existing_instance = self.instances.get_instance(requested_type, name)
        if existing_instance is not None:
            return existing_instance
        new_instance = await self._create_instance(requested_type, name)
        return new_instance

    def get(self, requested_type: TypeQuery[_T], name: ArgNameQuery = None) -> _T:
        """Retrieves an existing instance using type and optional name matching.

        This synchronous method looks up already-created instances in the container.
        Like `provide()`, it supports name-based resolution for distinguishing between
        multiple instances of the same type. Does not trigger instance creation.

        Args:
            requested_type: The type of the instance to retrieve.
            name: The argument name for named binding lookup. Enables retrieval
                of specific named instances when multiple bindings exist for the same type.

        Returns:
            The existing instance matching the type and name criteria.

        Raises:
            KeyError: If no matching instance is found. Use `provide()` to create
                new instances with automatic dependency resolution.
        """
        instance = self.instances.get_instance(requested_type, name)
        if instance is None:
            raise KeyError(f"Instance of {requested_type} is not found")
        return instance

    async def close(self) -> None:
        """Closes the container and cleans up all created instances."""
        await self.instances.close()

    async def _create_instance(self, requested_type: TypeQuery[_T], name: ArgNameQuery) -> _T:
        logger.debug("Creating instance of %s: %s...", name, requested_type)
        binding_record, (matched_type, matched_arg) = self.find_binding(requested_type, name)
        # the first argument can be used as a type of the dependency to be created
        # That's likely needs to be done only for predicate matching, but currently we can't distinguish them
        args_override = self._bind_factory_type_argument(matched_type, binding_record)
        args = await self._provide_dependencies(binding_record, args_override)
        instance: _T = await self.instances.create_instance(matched_type, matched_arg, binding_record, **args)
        logger.debug("Instance of %s: %s was created", matched_type, matched_arg)
        return instance

    async def _provide_dependencies(self, consumer: BindingRecord, args_override: dict[str, Any]) -> dict[str, Any]:
        args = self._list_dependencies(consumer, args_override)
        dependencies: dict[str, Any] = {}
        for arg_name, arg_type in args:
            # In theory, we can compose dependency graph
            # and visualize it with graphviz or something
            dependencies[arg_name] = await self.provide(arg_type, arg_name)
        dependencies |= args_override
        return dependencies

    @staticmethod
    def _list_dependencies(consumer: BindingRecord, args_override: dict[str, Any]) -> list[tuple[str, type]]:
        res: list[tuple[str, type]] = []
        signature = consumer.signature_info
        for parameter in signature.parameters.values():
            if (
                parameter.default == inspect.Parameter.empty
                and parameter.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
                and parameter.name not in args_override
                and parameter.annotation != inspect.Parameter.empty
            ):
                res.append((parameter.name, parameter.annotation))
        return res

    @staticmethod
    def _bind_factory_type_argument(type_to_create: type[Any] | None, binding_record: BindingRecord) -> dict[str, Any]:
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

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_details: Any) -> None:
        """Tear down all managed instances in LIFO order.

        Exceptions are forwarded to each managed instance's cleanup handler
        (`__exit__`, `__aexit__`). Return values from those handlers are
        intentionally ignored: no single managed object can suppress an exception on
        behalf of the whole container, ensuring the exception always propagates to
        the caller and all other cleanup handlers still receive it.
        """
        await self.instances.close(exc_details)
