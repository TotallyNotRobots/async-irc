# SPDX-FileCopyrightText: 2017-2020 Snoonet
# SPDX-FileCopyrightText: 2020-present linuxdaemon <linuxdaemon.irc@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Provides a Delayer object for delaying repeated calls e.g. server connections."""

import asyncio
import random
from collections.abc import Callable
from random import Random

from typing_extensions import Self

__all__ = ("AsyncDelayer",)


class AsyncDelayer:
    """Implementation of the exponential back-off algorithm for handling server reconnects.

    Implemented as a re-entrant async context manager so it can be used like so:
    >>> import asyncio  # doctest: +SKIP
    >>> async def connect() -> None: # doctest: +SKIP
    ...     delayer = AsyncDelayer()
    ...     connected = False
    ...     while not connected:
    ...         async with delayer:
    ...             # Attempt connection
    ...
    >>> loop = asyncio.get_event_loop()  # doctest: +SKIP
    >>> loop.run_until_complete(connect())  # doctest: +SKIP
    """

    def __init__(self, base: int = 1, *, integral: bool = False) -> None:
        """Configure delay options.

        Args:
            base: Base number to use in calculation. Defaults to 1.
            integral: Whether to use whole-second times or not. Defaults to False.
        """
        self._base: int = base
        self._integral: bool = integral
        self._max: int = 10
        self._exp: int = 0
        self._rand: Random = random.Random()  # noqa: S311
        self._rand.seed()

    @property
    def randfunc(self) -> Callable[[int, int], float]:
        """Which random function to use."""
        if self._integral:
            return self._rand.randrange

        return self._rand.uniform

    async def __aenter__(self) -> Self:
        """Enter delayed context.

        Sleeps for a random time according to the algorithm.
        """
        self._exp = min(self._exp + 1, self._max)
        wait = self.randfunc(0, self._base * (2**self._exp))  # pyright: ignore[reportAny]
        await asyncio.sleep(wait)
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Finalize delayed context."""
