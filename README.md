# async-irc [![Build Status](https://travis-ci.org/snoonetIRC/async-irc.svg?branch=master)](https://travis-ci.org/snoonetIRC/async-irc)
An implementation of asyncio.Protocol for IRC

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
