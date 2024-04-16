# async-irc
An implementation of asyncio.Protocol for IRC

[![CI - Test](https://github.com/TotallyNotRobots/async-irc/actions/workflows/python-tests.yml/badge.svg)](https://github.com/TotallyNotRobots/async-irc/actions/workflows/python-tests.yml)
[![CD - Build](https://github.com/TotallyNotRobots/async-irc/actions/workflows/python-publish.yml/badge.svg)](https://github.com/TotallyNotRobots/async-irc/actions/workflows/python-publish.yml)
[![codecov](https://codecov.io/gh/TotallyNotRobots/async-irc/graph/badge.svg?token=Gz8jBOG9js)](https://codecov.io/gh/TotallyNotRobots/async-irc)

[![PyPI - Version](https://img.shields.io/pypi/v/async-irc.svg)](https://pypi.org/project/async-irc/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/async-irc.svg)](https://pypi.org/project/async-irc/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/async-irc.svg)](https://pypi.org/project/async-irc/)

[![linting - Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![types - Mypy](https://img.shields.io/badge/types-Mypy-blue.svg)](https://github.com/python/mypy)

[![License - MIT](https://img.shields.io/badge/license-MIT-9400d3.svg)](https://spdx.org/licenses/)

## Using the library
- You can install the library using pip: `pip install async-irc`

### Example
```python
import asyncio

from asyncirc.protocol import IrcProtocol
from asyncirc.server import Server

loop = asyncio.get_event_loop()

servers = [
    Server("irc.example.org", 6697, True),
    Server("irc.example.com", 6667),
]

async def log(conn, message):
    print(message)

async def main():
    conn = IrcProtocol(servers, "BotNick", loop=loop)
    conn.register_cap('userhost-in-names')
    conn.register('*', log)
    await conn.connect()
    await asyncio.sleep(24 * 60 * 60)

try:
    loop.run_until_complete(main())
finally:
    loop.stop()
```
