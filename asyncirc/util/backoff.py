import asyncio
import random


class AsyncDelayer:
    """Implementation of the exponential back-off algorithm for handling server reconnects

    Implemented as a reentrant async context manager so it can be used like so:
    >>> delayer = AsyncDelayer()
    >>> async with delayer:
    ...     # Operation to be delayed
    """

    def __init__(self, base=1, *, integral=False):
        self._base = base
        self._integral = integral
        self._max = 10
        self._exp = 0
        self._rand = random.Random()
        self._rand.seed()

    @property
    def randfunc(self):
        return self._rand.randrange if self._integral else self._rand.uniform

    async def __aenter__(self):
        self._exp = min(self._exp + 1, self._max)
        wait = self.randfunc(0, self._base * (2 ** self._exp))
        await asyncio.sleep(wait)
        return self

    async def __aexit__(self, *exc):
        pass
