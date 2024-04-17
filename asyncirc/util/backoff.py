"""Provides a Delayer object for delaying repeated calls e.g. server connections."""

import asyncio
import random
from typing import Callable

__all__ = ("AsyncDelayer",)


class AsyncDelayer:
    """Implementation of the exponential back-off algorithm for handling server reconnects.

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
        """Configure delay options.

        Args:
            base: Base number to use in calculation. Defaults to 1.
            integral: Whether to use whole-second times or not. Defaults to False.
        """
        self._base = base
        self._integral = integral
        self._max = 10
        self._exp = 0
        self._rand = random.Random()
        self._rand.seed()

    @property
    def randfunc(self) -> Callable[[int, int], float]:
        """Which random function to use."""
        if self._integral:
            return self._rand.randrange

        return self._rand.uniform

    async def __aenter__(self) -> "AsyncDelayer":
        """Enter delayed context.

        Sleeps for a random time according to the algorithm.
        """
        self._exp = min(self._exp + 1, self._max)
        wait = self.randfunc(0, self._base * (2**self._exp))
        await asyncio.sleep(wait)
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Finalize delayed context."""
