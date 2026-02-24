import inspect
from functools import partial
from types import UnionType
from typing import Any, Awaitable, Callable, Generic, NamedTuple, TypeVar, Union, cast, get_origin, overload

from .dimap import DIMap, DIMapKey, TypeQuery


class _MissingType:
    pass


_MISSING = _MissingType()

_T = TypeVar("_T")
# bind(...) types
FactoryFunc = Callable[..., _T] | Callable[..., Awaitable[_T]]
BindingTarget = _T | FactoryFunc[_T]
TypeMatcher = Callable[[type[_T]], bool]
TypeSelector = type[_T] | TypeMatcher[_T] | None


class BindingRecord(NamedTuple, Generic[_T]):
    async_factory: Callable[..., Awaitable[_T]] | None
    sync_factory: Callable[..., _T] | None
    signature_info: inspect.Signature
    # todo: signature info (e.g. if type is passed as an argument to the factory)

    def call_sync(self, *args: Any, **kwargs: Any) -> _T:
        if self.sync_factory is None:
            raise RuntimeError("synchronous calls are not supported")
        return self.sync_factory(*args, **kwargs)

    async def call_async(self, *args: Any, **kwargs: Any) -> _T:
        if self.sync_factory is not None:
            return self.call_sync(*args, **kwargs)
        if self.async_factory is None:
            raise RuntimeError("no factory function is available")
        return await self.async_factory(*args, **kwargs)

class FactoryBox:
    """
    Container serving as a registry for factory functions.

    Each registered binding associates a selector (what is requested) with a target (how it is
    provided).

    Selectors:
        - by specific class/type.
        - by argument name and a type (for named dependencies).
        - by predicate — a callable ``(requested_type) -> bool`` used to match types.

    Targets:
        - Concrete class or constructor: the class itself is used as a sync factory.
        - Factory callable: a sync or async function that returns an instance.
        - Instance: a pre-created value returned as-is.

    """

    def __init__(self):
        self.map: DIMap[BindingRecord[Any]] = DIMap()  # type -> Binding
        self.func_matchers: list[tuple[TypeMatcher[Any], BindingRecord[Any]]] = []  # predicate -> Binding

    @overload
    def bind(self, type_selector: TypeSelector[_T], target: BindingTarget[_T], **kwargs: Any) -> None: ...

    @overload
    def bind(self, type_selector: type[_T], argname: str, target: BindingTarget[_T], **kwargs: Any) -> None: ...

    @overload
    def bind(
        self, type_selector: TypeSelector[_T] = None, argname: str | None = None, *, factory: FactoryFunc[_T], **kwargs: Any
    ) -> None: ...

    @overload
    def bind(
        self, type_selector: TypeSelector[_T] = None, argname: str | None = None, *, instance: _T, **kwargs: Any
    ) -> None: ...

    def bind(
        self,
        *args: Any,
        type_selector: TypeSelector[_T] | None | _MissingType = _MISSING,
        argname: str | None | _MissingType = _MISSING,
        target: BindingTarget[_T] | _MissingType = _MISSING,
        factory: FactoryFunc[_T] | _MissingType = _MISSING,
        instance: _T | _MissingType = _MISSING,
        **kwargs: Any,
    ) -> None:
        """

        Register a binding between a selector (a type or a predicate) and a target
        (a factory function, an instance, or a specific implementation).

        A binding defines how a requested dependency is provided. Selectors
        (type, type+argname, or predicate) determine when the binding applies; targets determine
        what is returned (a class/constructor, a factory callable, or a pre-built
        instance). Exactly one of ``target``, ``factory``, or ``instance`` must be
        provided. Positional shorthand forms used in the Examples are supported but
        must not be mixed with the keyword-style call forms.

        Examples:

        ```python˘˘
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
            argname: Optional name for a named binding.
            target: Class or callable used as the binding target.
            factory: Explicit factory callable (sync or async).
            instance: Pre-created instance to return.
            **kwargs: Keyword arguments forwarded to the factory when called.

        Notes:
            - Extra keyword arguments passed to ``bind`` are forwarded to the factory when called.
        """
        type_selector, argname, factory_record = _dispatch_arguments(
            args, kwargs, type_selector, argname, target, factory, instance
        )
        self._add_binding(type_selector, argname, factory_record)

    def find_binding(
        self, requested_type: TypeQuery[_T] | None, argname: str | None
    ) -> tuple[BindingRecord[_T], DIMapKey[_T]]:
        # look in the map type->binding
        match = self.map.find_match(requested_type, argname)
        if match is not None:
            return match
        # try predicate-based bindings
        origin_type = get_origin(requested_type)
        if requested_type is None or origin_type == UnionType or origin_type == Union:
            raise ValueError(f"No binding found for ({requested_type}, {argname})")
        for type_matcher, factory in self.func_matchers:
            if type_matcher(requested_type):
                return factory, (requested_type, None) # type: ignore - it's not an union nor none
        # return requested type as a factory if it's a class and no other match is found
        if not inspect.isclass(requested_type):
            raise ValueError(f"No binding found for ({requested_type}, {argname})")
        return _wrap_factory_func(requested_type), (requested_type, None)

    def _add_binding(
        self, type_selector: TypeSelector[_T], argname: str | None, factory_record: BindingRecord[_T],
    ):
        type_predicate = cast(TypeMatcher[_T], type_selector) if inspect.isfunction(type_selector) else None
        if type_predicate is not None:
            if argname is not None:
                raise ValueError("argname is not allowed when binding to a function")
            self.func_matchers.append((type_predicate, factory_record))
        else:
            self.map[type_selector, argname] = factory_record

def _dispatch_arguments(
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    type_selector: TypeSelector[_T] | None | _MissingType = _MISSING,
    argname: str | None | _MissingType = _MISSING,
    target: BindingTarget[_T] | _MissingType = _MISSING,
    factory: FactoryFunc[_T] | _MissingType = _MISSING,
    instance: _T | _MissingType = _MISSING,
)-> tuple[TypeSelector[_T], str | None, BindingRecord[_T]]:
    arg_count = len(args)
    if arg_count == 3:
        # bind(type_selector, argname, target, **kwargs)
        _forbid_kwargs(type_selector, argname, target)
        type_selector, argname, target = args
    elif arg_count == 2:
        # Could be: bind(type_selector, target) or bind(type_selector, argname, *, target/factory/instance=...)
        if factory is not _MISSING or instance is not _MISSING or target is not _MISSING:
            # bind(type_selector, argname, target/factory/instance=...)
            _forbid_kwargs(type_selector, argname)
            type_selector, argname = args
        else:
            # bind(type_selector, target)
            _forbid_kwargs(type_selector, argname)
            type_selector, target = args
            if argname is _MISSING:
                argname = None
    elif arg_count == 1:
        # bind(type_selector, target/factory/instance=...) or bind(type_selector, argname=..., factory/instance=...)
        _forbid_kwargs(type_selector)
        type_selector = args[0]
    elif arg_count == 0:
        # All arguments are keyword-only
        ...
    else:
        raise TypeError(f"bind() takes at most 3 positional arguments ({arg_count} given)")

    if argname is _MISSING:
        argname = None
    if type_selector is _MISSING:
        type_selector = None

    if sum(1 for t in (target, factory, instance) if t is not _MISSING) > 1:
        raise TypeError("Exactly one of target, factory, or instance must be provided")
    if target is not _MISSING:
        factory_record = _wrap_generic_target(cast(BindingTarget[_T], target), **kwargs)
    elif factory is not _MISSING:
        factory_record = _wrap_factory_func(cast(FactoryFunc[_T], factory), **kwargs)
    elif instance is not _MISSING:
        factory_record = _wrap_instance(cast(_T, instance), **kwargs)
    else:
        raise TypeError("Either target, factory, or instance must be provided")

    return cast(TypeSelector[_T], type_selector), cast(str | None, argname), factory_record


def _wrap_factory_func(func: FactoryFunc[_T], **kwargs: Any) -> BindingRecord[_T]:
    func = cast(FactoryFunc[_T], func if not kwargs else partial(func, **kwargs))
    if inspect.iscoroutinefunction(func):
        # If it's a coroutine function, we can only support async calls.
        async_factory = cast(Callable[..., Awaitable[_T]], func)
        return BindingRecord(async_factory=async_factory, sync_factory=None, signature_info=inspect.signature(func))
    else:
        # it's a sync factory, we can wrap it to support async calls as well.
        sync_factory = cast(Callable[..., _T], func)
        return BindingRecord(async_factory=None, sync_factory=sync_factory, signature_info=inspect.signature(func))


def _wrap_instance(instance: _T, **kwargs: Any) -> BindingRecord[_T]:
    if kwargs:
        raise ValueError("Cannot pass kwargs when binding to an instance")

    def sync_factory():
        return instance

    return BindingRecord(async_factory=None, sync_factory=sync_factory, signature_info=inspect.Signature())


def _wrap_generic_target(target: BindingTarget[_T], **kwargs: Any) -> BindingRecord[_T]:
    if callable(target):
        return _wrap_factory_func(cast(FactoryFunc[_T], target), **kwargs)
    else:
        return _wrap_instance(cast(_T, target), **kwargs)


def _forbid_kwargs(*args: Any):
    if any(arg is not _MISSING for arg in args):
        raise TypeError("keyword arguments are incompatible with the used positional argument form")