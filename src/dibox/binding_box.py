import inspect
from contextlib import AbstractAsyncContextManager, AbstractContextManager, asynccontextmanager, contextmanager
from functools import partial
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterator,
    Awaitable,
    Callable,
    Generator,
    Iterator,
    NamedTuple,
    TypeVar,
    cast,
    overload,
)

from .dimap import ANY_ARG, ANY_TYPE, DIMap, DIMapKey, TypeQuery, WildArgName, WildType


class _MissingType:
    pass

_MISSING = _MissingType()

_T = TypeVar("_T")
# bind(...) types
FactoryFunc = (
    Callable[..., _T]
    | Callable[..., Awaitable[_T]]
    | Callable[..., AbstractContextManager[_T]]  # probably we should add small protocols for sync/async context managers
    | Callable[..., AbstractAsyncContextManager[_T]]
    | Callable[..., Generator[_T, None, None]]
    | Callable[..., AsyncGenerator[_T, None]]
)
BindingTarget = _T | FactoryFunc[_T]
TypeMatchPredicate = Callable[[type[_T]], bool]


class BindingRecord(NamedTuple):
    async_factory: Callable[..., Awaitable[Any]] | None
    sync_factory: Callable[..., Any] | None
    signature_info: inspect.Signature
    # todo: calling protocol (e.g. if type is passed as an argument to the factory)

    def call_sync(self, *args: Any, **kwargs: Any) -> Any:
        if self.sync_factory is not None:
            return self.sync_factory(*args, **kwargs)
        raise RuntimeError("synchronous calls are not supported")

    async def call_async(self, *args: Any, **kwargs: Any) -> Any:
        if self.async_factory is not None:
            return await self.async_factory(*args, **kwargs)
        if self.sync_factory is not None:
            return self.call_sync(*args, **kwargs)
        raise RuntimeError("no factory function is available")


class BindingBox:
    """
    Container serving as a registry for factory functions.

    Each registered binding associates a selector (what is requested) with a target (how it is
    provided). Most commonly, the selector is a type or an (type, argument name) pair, but it
    can also be a predicate function that ``(requested_type) -> bool``.
    The target can be a concrete class, a factory function (including yield and context managers),
    or a pre-created instance.
    """

    def __init__(self) -> None:
        self.map: DIMap[BindingRecord] = DIMap()  # type -> Binding
        self.func_matchers: list[tuple[TypeMatchPredicate[Any], BindingRecord]] = []  # predicate -> Binding

    # --- Bind overloads ---
    @overload
    def bind(
        self,
        type_selector: type[_T],
        **kwargs: Any,
    ) -> None: ...

    @overload
    def bind(
        self,
        type_selector: WildType[_T] | TypeMatchPredicate[_T],
        target: BindingTarget[_T],
        **kwargs: Any,
    ) -> None: ...

    @overload
    def bind(
        self,
        type_selector: WildType[_T],
        name: WildArgName,
        target: BindingTarget[_T],
        **kwargs: Any,
    ) -> None: ...

    @overload
    def bind(
        self,
        type_selector: WildType[_T] | TypeMatchPredicate[_T] = ANY_TYPE,
        name: WildArgName = ANY_ARG,
        *,
        target: BindingTarget[_T],
        **kwargs: Any,
    ) -> None: ...

    @overload
    def bind(
        self,
        type_selector: WildType[_T] | TypeMatchPredicate[_T] = ANY_TYPE,
        name: WildArgName = ANY_ARG,
        *,
        factory: FactoryFunc[_T],
        **kwargs: Any,
    ) -> None: ...

    @overload
    def bind(
        self,
        type_selector: WildType[_T] | TypeMatchPredicate[_T] = ANY_TYPE,
        name: WildArgName = ANY_ARG,
        *,
        instance: _T,
        **kwargs: Any,
    ) -> None: ...

    def bind(
        self,
        *args: Any,
        type_selector: WildType[_T] | TypeMatchPredicate[_T] | _MissingType = _MISSING,
        name: WildArgName | _MissingType = _MISSING,
        target: BindingTarget[_T] | _MissingType = _MISSING,
        factory: FactoryFunc[_T] | _MissingType = _MISSING,
        instance: _T | _MissingType = _MISSING,
        **kwargs: Any,
    ) -> None:
        """

        Register a binding between a selector (a type or a predicate) and a target
        (a factory function, an instance, or a specific implementation).

        A binding defines how a requested dependency is provided. Selectors
        (type, type+name, or predicate) determine when the binding applies; targets determine
        what is returned (a class/constructor, a factory callable, or a pre-built
        instance). Exactly one of ``target``, ``factory``, or ``instance`` must be
        provided. Positional shorthand forms used in the Examples are supported but
        must not be mixed with the keyword-style call forms.

        Examples:

        ```python˘˘
        # Self-binding
        bind(Service)

        # Type -> implementation or factory
        bind(Service, ServiceImpl)
        bind(Service, lambda: ServiceImpl())

        # Named binding
        bind(Database, "primary_db", production_database)

        # Factory binding
        bind(Service, factory=lambda: ServiceImpl())
        bind(Service, "db_service", factory=create_db_service)

        # Instance binding
        bind(Config, instance=Config("prod"))
        bind(Database, "cache_db", instance=redis_db)

        # Predicate-based binding
        bind(lambda t: t.__name__.endswith("Settings"), load_settings)
        ```

        Args:
            *args: Positional convenience forms (see Examples).
            type_selector: Type or predicate selecting which requested types match.
            name: Optional name for a named binding.
            target: Class or callable used as the binding target.
            factory: Explicit factory callable (sync or async).
            instance: Pre-created instance to return.
            **kwargs: Keyword arguments forwarded to the factory when called.

        Notes:
            - Extra keyword arguments passed to ``bind`` are forwarded to the factory when called.
        """
        type_selector, name, factory_record = _dispatch_bind_arguments(
            args, kwargs, type_selector, name, target, factory, instance
        )
        self._add_binding(type_selector, name, factory_record)

    def bind_many(self, *types: type[Any]) -> None:
        """Convenience method to self-bind multiple types at once.

        Equivalent to calling ``bind(T)`` for each provided type.
        Useful in strict mode to reduce boilerplate when registering many concrete services.
        """
        for t in types:
            self.bind(t)

    def find_binding(
        self, requested_type: TypeQuery[Any], name: WildArgName
    ) -> tuple[BindingRecord | None, DIMapKey[Any]]:
        # look in the map type->binding
        matched_binding, matched_key = self.map.find_match(requested_type, name)
        if matched_binding is not None:
            return matched_binding, matched_key
        # try predicate-based bindings
        if isinstance(requested_type, type):
            for type_matcher, factory in self.func_matchers:
                if type_matcher(requested_type):
                    return factory, (requested_type, ANY_ARG)
        return None, (ANY_TYPE, ANY_ARG)

    def _add_binding(
        self, type_selector: WildType[_T] | TypeMatchPredicate[_T], name: WildArgName, factory_record: BindingRecord,
    ) -> None:
        if inspect.isfunction(type_selector):
            if name is not ANY_ARG:
                raise ValueError("name is not allowed when binding to a function")
            type_predicate = cast(TypeMatchPredicate[_T], type_selector)
            self.func_matchers.append((type_predicate, factory_record))
        else:
            self.map[cast(WildType[_T], type_selector), name] = factory_record

def _dispatch_bind_arguments(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    type_selector: WildType[_T] | TypeMatchPredicate[_T] | _MissingType = _MISSING,
    name: WildArgName | _MissingType = _MISSING,
    target: BindingTarget[_T] | _MissingType = _MISSING,
    factory: FactoryFunc[_T] | _MissingType = _MISSING,
    instance: _T | _MissingType = _MISSING,
)-> tuple[WildType[_T] | TypeMatchPredicate[_T], WildArgName, BindingRecord]:
    arg_count = len(args)
    if arg_count == 3:
        # bind(type_selector, name, target, **kwargs)
        _forbid_kwargs(type_selector, name, target)
        type_selector, name, target = args
    elif arg_count == 2:
        # Could be: bind(type_selector, target) or bind(type_selector, name, *, target/factory/instance=...)
        if factory is not _MISSING or instance is not _MISSING or target is not _MISSING:
            # bind(type_selector, name, target/factory/instance=...)
            _forbid_kwargs(type_selector, name)
            type_selector, name = args
        else:
            # bind(type_selector, target)
            _forbid_kwargs(type_selector, name)
            type_selector, target = args
            if name is _MISSING:
                name = ANY_ARG
    elif arg_count == 1:
        # bind(type_selector, target/factory/instance=...) or bind(type_selector, name=..., factory/instance=...)
        # or bind(type_selector)
        _forbid_kwargs(type_selector)
        type_selector = args[0]
        if factory is _MISSING and instance is _MISSING and target is _MISSING and name is _MISSING:
            # bind(type_selector)
            if isinstance(type_selector, type):
                target = type_selector
    elif arg_count == 0:
        # All arguments are keyword-only
        ...
    else:
        raise TypeError(f"bind() takes at most 3 positional arguments ({arg_count} given)")

    if name is _MISSING:
        name = ANY_ARG
    if type_selector is _MISSING:
        type_selector = ANY_TYPE

    if sum(1 for t in (target, factory, instance) if t is not _MISSING) > 1:
        raise TypeError("Exactly one of target, factory, or instance must be provided")
    if target is not _MISSING:
        factory_record = _create_binding_record_for_generic_target(cast(BindingTarget[_T], target), **kwargs)
    elif factory is not _MISSING:
        factory_record = _create_binding_record_for_factory(cast(FactoryFunc[_T], factory), **kwargs)
    elif instance is not _MISSING:
        factory_record = _create_binding_record_for_instance(cast(_T, instance), **kwargs)
    else:
        raise TypeError("Either target, factory, or instance must be provided")

    return type_selector, name, factory_record # type: ignore[return-value]


def _create_binding_record_for_factory(func: FactoryFunc[Any], **kwargs: Any) -> BindingRecord:
    func = cast(FactoryFunc[Any], func if not kwargs else partial(func, **kwargs))
    if inspect.isasyncgenfunction(func):
        func = asynccontextmanager(cast(Callable[..., AsyncIterator[Any]], func))
    elif inspect.isgeneratorfunction(func):
        func = contextmanager(cast(Callable[..., Iterator[Any]], func))
    if inspect.iscoroutinefunction(func):
        # If it's a coroutine function, we can only support async calls.
        async_factory = cast(Callable[..., Awaitable[Any]], func)
        return BindingRecord(async_factory=async_factory, sync_factory=None, signature_info=inspect.signature(func))
    else:
        # it's a sync factory, we can wrap it to support async calls as well.
        sync_factory = cast(Callable[..., Any], func)
        return BindingRecord(async_factory=None, sync_factory=sync_factory, signature_info=inspect.signature(func))


def _create_binding_record_for_instance(instance: Any, **kwargs: Any) -> BindingRecord:
    if kwargs:
        raise ValueError("Cannot pass kwargs when binding to an instance")

    def sync_factory() -> Any:
        return instance

    return BindingRecord(async_factory=None, sync_factory=sync_factory, signature_info=inspect.Signature())


def _create_binding_record_for_generic_target(target: BindingTarget[_T], **kwargs: Any) -> BindingRecord:
    if callable(target):
        return _create_binding_record_for_factory(target, **kwargs)
    else:
        return _create_binding_record_for_instance(target, **kwargs)


def _forbid_kwargs(*args: Any) -> None:
    if any(arg is not _MISSING for arg in args):
        raise TypeError("keyword arguments are incompatible with the used positional argument form")