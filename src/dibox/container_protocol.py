from typing import Protocol, TypeVar

from .dimap import ArgNameQuery, TypeQuery

_T = TypeVar("_T")


class ContainerProtocol(Protocol):
    def get(self, requested_type: TypeQuery[_T], name: ArgNameQuery = None) -> _T:
        ...

    async def provide(self, requested_type: TypeQuery[_T], name: ArgNameQuery = None) -> _T:
        ...