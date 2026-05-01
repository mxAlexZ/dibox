from typing import Protocol, TypeVar

from .dimap import ANY_ARG, TypeQuery, WildArgName

_T = TypeVar("_T")


class ContainerProtocol(Protocol):
    def get(self, requested_type: TypeQuery[_T], name: WildArgName = ANY_ARG) -> _T:
        ...

    async def provide(self, requested_type: TypeQuery[_T], name: WildArgName = ANY_ARG) -> _T:
        ...