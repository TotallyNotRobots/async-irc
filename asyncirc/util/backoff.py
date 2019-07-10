# coding=utf-8
"""
Provides a Delayer object for delaying repeated calls e.g. server connections
"""

import asyncio
import random
from typing import Any, Callable

__all__ = ('AsyncDelayer',)


class AsyncDelayer:
    """Implementation of the exponential back-off algorithm for handling server reconnects

    Implemented as a re-entrant async context manager so it can be used like so:
    >>> import asyncio
    >>> async def connect() -> None:
    ...     delayer = AsyncDelayer()
    ...     connected = False
    ...     while not connected:
    ...         async with delayer:
    ...             # Attempt connection
    ...
    >>> loop = asyncio.get_event_loop()
    >>> loop.run_until_complete(connect())
    """

    def __init__(self, base: int = 1, *, integral: bool = False) -> None:
        self._base = base
        self._integral = integral
        self._max = 10
        self._exp = 0
        self._rand = random.Random()
        self._rand.seed()

    @property
    def randfunc(self) -> Callable:
        return self._rand.randrange if self._integral else self._rand.uniform

    async def __aenter__(self) -> 'AsyncDelayer':
        self._exp = min(self._exp + 1, self._max)
        wait = self.randfunc(0, self._base * (2 ** self._exp))
        await asyncio.sleep(wait)
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        pass
