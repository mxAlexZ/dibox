import inspect
import logging
from contextvars import ContextVar, Token
from typing import Any, Awaitable, Callable, ClassVar, TypeGuard, TypeVar, get_origin, overload

from .binding_box import BindingBox, BindingRecord
from .dimap import ArgNameQuery, DIMapKey, TypeQuery
from .injector import Injector
from .instance_box import InstanceBox
from .resolution_error import ResolutionError
from .resolution_stack import ResolutionStack, format_frame, format_type

_T = TypeVar("_T")
_R = TypeVar("_R")
logger = logging.getLogger(__name__)


class DIBox(BindingBox):
    """A dependency injection container.

    `DIBox` is responsible for creating and managing the lifecycle of objects
    (called "services" or "dependencies"). It can automatically resolve and
    inject dependencies for requested types.

    It works as an async context manager, allowing for proper cleanup of
    resources.
    """

    _context_box: ClassVar[ContextVar["DIBox"]] = ContextVar("dibox")

    def __init__(self, strict: bool = False) -> None:
        self.instances = InstanceBox()
        self.injector = Injector(self)
        self.modules: list[BindingBox] = []
        self._context_token: Token["DIBox"] | None = None
        self._is_strict = strict
        super().__init__()

    @classmethod
    def from_context(cls) -> "DIBox":
        """Returns the container currently active in this context.

        Raises:
            RuntimeError: If no container is active. Use `async with box:` to activate one.
        """
        try:
            return cls._context_box.get()
        except LookupError:
            raise RuntimeError("No active container — use 'async with box:' first")

    def add_bindings(self, binding_box: BindingBox) -> None:
        """Registers a reusable binding module (`BindingBox`) on this container.

        A module is a portable set of binding rules that can be shared across
        contexts (for example, app entry points, workers, and tests).

        Resolution order is explicit:
        - direct container bindings added via `bind()` have highest precedence,
        - added modules are searched in reverse registration order,
        - among modules, the last added wins.

        Args:
            binding_box: Module to append to the container's module chain.
        """
        self.modules.append(binding_box)

    def find_binding(
        self, requested_type: TypeQuery[Any] | None, name: str | None
    ) -> tuple[BindingRecord | None, DIMapKey[Any]]:
        binding_record, key = super().find_binding(requested_type, name)
        if binding_record is not None:
            return binding_record, key
        for module in reversed(self.modules):
            binding_record, key = module.find_binding(requested_type, name)
            if binding_record is not None:
                return binding_record, key
        return None, (None, None)  # no binding found

    def inject(self, func: Callable[..., _R]) -> Callable[..., _R]:
        """Decorates a function so missing injectable arguments come from this container.

        Only parameters marked with `Injected[...]` are injected.

        The wrapped function keeps its runtime behavior, but injected
        parameters are removed from the visible signature. This is useful for
        framework entry points that inspect signatures (for example, web or CLI
        handlers).
        """
        return self.injector.inject(func)

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
        return await self._get_or_create_instance(requested_type, name, resolution_stack=[])

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

    async def _get_or_create_instance(
        self,
        requested_type: TypeQuery[_T],
        name: ArgNameQuery,
        resolution_stack: ResolutionStack,
    ) -> _T:
        existing_instance = self.instances.get_instance(requested_type, name)
        if existing_instance is not None:
            return existing_instance
        new_instance = await self._create_instance(requested_type, name, resolution_stack)
        return new_instance

    async def _create_instance(
        self,
        requested_type: TypeQuery[_T],
        name: ArgNameQuery,
        resolution_stack: ResolutionStack,
    ) -> _T:
        resolution_stack.append((requested_type, name))
        try:
            binding_record, (matched_type, matched_arg) = self.find_binding(requested_type, name)
            if binding_record is None:
                # implicit self-binding for concrete classes in non-strict mode
                binding_record, matched_type = self._make_impicit_binding_record(requested_type, resolution_stack)
                matched_arg = None
            if logger.isEnabledFor(logging.DEBUG):
                parent = resolution_stack[-2] if len(resolution_stack) > 1 else None
                parent_part = f" (as dependency of {format_type(parent[0])})" if parent is not None else ""
                requested = format_frame(requested_type, name)
                logger.debug("Creating instance %s %s", requested, parent_part)
            # the first argument can be used as a type of the dependency to be created
            # That's likely needs to be done only for predicate matching, but currently we can't distinguish them
            args_override = self._bind_factory_type_argument(matched_type, binding_record)
            args = await self._provide_dependencies(binding_record, args_override, resolution_stack)
        finally:
            resolution_stack.pop()
        instance: _T = await self.instances.create_instance(matched_type, matched_arg, binding_record, **args)
        return instance

    def _make_impicit_binding_record(
        self,
        requested_type: TypeQuery[_T],
        resolution_stack: ResolutionStack,
    ) -> tuple[BindingRecord, type[_T]]:
        if not self._is_autowireable(requested_type):
            reason = "no binding found" if self._is_strict else "requested type is not a concrete class"
            raise ResolutionError(reason, resolution_stack)
        binding_record = BindingRecord(
            async_factory=None, sync_factory=requested_type, signature_info=inspect.signature(requested_type)
        )
        return binding_record, requested_type

    def _is_autowireable(self, requested_type: TypeQuery[Any]) -> TypeGuard[type]:
        if self._is_strict or not isinstance(requested_type, type):
            return False
        try:
            _ = inspect.signature(requested_type)
        except (ValueError, TypeError):
            # C extensions, special forms — treat as blacklisted
            return False
        return True

    async def _provide_dependencies(
        self,
        consumer: BindingRecord,
        args_override: dict[str, Any],
        resolution_stack: ResolutionStack,
    ) -> dict[str, Any]:
        args = self._list_dependencies(consumer, args_override)
        dependencies: dict[str, Any] = {}
        for arg_name, arg_type in args:
            dependencies[arg_name] = await self._get_or_create_instance(arg_type, arg_name, resolution_stack)
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

    async def __aenter__(self) -> "DIBox":
        self._context_token = DIBox._context_box.set(self)
        return self

    async def __aexit__(self, *exc_details: Any) -> None:
        """Tear down all managed instances in LIFO order.

        Exceptions are forwarded to each managed instance's cleanup handler
        (`__exit__`, `__aexit__`). Return values from those handlers are
        intentionally ignored: no single managed object can suppress an exception on
        behalf of the whole container, ensuring the exception always propagates to
        the caller and all other cleanup handlers still receive it.
        """
        if self._context_token is not None:
            DIBox._context_box.reset(self._context_token)
            self._context_token = None
        await self.instances.close(exc_details)
