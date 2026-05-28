import logging
from contextvars import ContextVar, Token
from typing import Any, Awaitable, Callable, ClassVar, Self, TypeVar, overload

from .binding_box import BindingBox, BindingMatch
from .dependency_graph import DependencyGraph, ResolutionMode, WalkResult
from .dimap import ANY_ARG, MatchAny, TypeQuery, WildArgName
from .injector import Injector
from .instance_box import InstanceBox
from .resolution_stack import ResolutionStack, format_frame, format_resolution_path, format_type

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

    def __init__(self, mode: ResolutionMode = "permissive") -> None:
        self.instances = InstanceBox()
        self.injector = Injector(self)
        self.modules: list[BindingBox] = []
        self._context_token: Token["DIBox"] | None = None
        self._resolution_mode = mode
        self._dependency_graph = DependencyGraph(mode, bindings=self)
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

    def find_binding(self, requested_type: TypeQuery[Any], arg_name: WildArgName) -> BindingMatch | None:
        binding_match = super().find_binding(requested_type, arg_name)
        if binding_match is not None:
            return binding_match
        for module in reversed(self.modules):
            binding_match = module.find_binding(requested_type, arg_name)
            if binding_match is not None:
                return binding_match
        return None

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

    @overload
    async def provide(self, requested_type: MatchAny, arg_name: str) -> Any: ...
    @overload
    async def provide(self, requested_type: TypeQuery[_T], arg_name: WildArgName = ANY_ARG) -> _T: ...

    async def provide(self, requested_type: TypeQuery[_T], arg_name: WildArgName = ANY_ARG) -> _T:
        """Provides an instance of the requested type, with optional name-based binding.

        This is the primary method for dependency resolution. DIBox matches dependencies
        using both type and argument name, enabling named bindings where multiple instances
        of the same type can be distinguished by parameter names.

        If a matching instance already exists, it will be returned. Otherwise, DIBox will
        create a new instance, automatically resolving and injecting all its dependencies
        based on constructor type hints. Supports async factories and lifecycle management.

        Args:
            requested_type: The type of the instance to provide.
            name: The argument name for named binding resolution. When provided,
                DIBox first attempts to match both type and name, falling back to
                type-only matching if no named binding exists.

        Returns:
            The existing or freshly created instance matching the type and name criteria.
        """
        existing_instance = self.instances.get_instance(requested_type, arg_name)
        if existing_instance is not None:
            return existing_instance
        root_node = self._dependency_graph.build_node((requested_type, arg_name))
        graph_steps = self._dependency_graph.walk(root_node, present_map=self.instances.index)
        for step in graph_steps:
            await self._create_instance(step)
        instance = self.instances.index[root_node.key]
        return instance

    def get(self, requested_type: TypeQuery[_T], arg_name: WildArgName = ANY_ARG) -> _T:
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
        instance = self.instances.get_instance(requested_type, arg_name)
        if instance is None:
            raise KeyError(f"Instance of {requested_type} is not found")
        return instance

    async def close(self) -> None:
        """Closes the container and cleans up all created instances."""
        await self.instances.close()

    async def _create_instance(self, walk_step: WalkResult) -> object:
        _log_instance_creation(*walk_step.node_key, walk_step.resolution_stack)
        args: dict[str, object] = {}
        for name, sub_node_key in walk_step.dependencies.items():
            args[name] = self.instances.index[sub_node_key]
        try:
            return await self.instances.create_instance(*walk_step.node_key, walk_step.binding, **args)
        except Exception as error:
            error.add_note(f"Resolution path:\n{format_resolution_path(walk_step.resolution_stack)}")
            raise

    async def __aenter__(self) -> Self:
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


def _log_instance_creation(
    requested_type: TypeQuery[_T],
    name: WildArgName,
    resolution_stack: ResolutionStack,
) -> None:
    if logger.isEnabledFor(logging.DEBUG):
        parent = resolution_stack[-2] if len(resolution_stack) > 1 else None
        parent_part = f" (from {format_type(parent[0])})" if parent is not None else ""
        requested = format_frame(requested_type, name)
        logger.debug("Creating instance of %s%s", requested, parent_part)
