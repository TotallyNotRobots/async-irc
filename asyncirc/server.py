# coding=utf-8
"""
Server objects used for different stages in the connect process
to store contextual data
"""
import asyncio
import ssl
from typing import Dict, Optional, Tuple

from irclib.parser import Cap

__all__ = (
    'BaseServer',
    'Server',
    'BasicIPServer',
    'BasicUNIXServer',
    'ConnectedServer',
    'BadAttribute',
)


class BaseServer:
    def __init__(
        self,
        *,
        password: str = None,
        is_ssl: bool = False,
        ssl_ctx: ssl.SSLContext = None,
        certpath: str = None,
    ):
        if is_ssl:
            if ssl_ctx is None:
                ssl_ctx = ssl.create_default_context()

            if certpath:
                ssl_ctx.load_cert_chain(certpath)

            self.ssl_ctx = ssl_ctx
        else:
            self.ssl_ctx = None

        self.password = password

    @property
    def is_ssl(self):
        return self.ssl_ctx is not None

    async def connect(self, protocol_factory, *, loop=None, **kwargs):
        raise NotImplementedError

    async def do_connect(self, protocol_factory, *, loop=None):
        return await self.connect(protocol_factory, loop=loop, ssl=self.ssl_ctx)

    def __str__(self) -> str:
        raise NotImplementedError


class BasicIPServer(BaseServer):
    """A simple implementation for connecting to a normal TCP server"""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        is_ssl: bool = False,
        password: str = None,
        ssl_ctx: ssl.SSLContext = None,
        certpath: str = None,
    ) -> None:
        super().__init__(
            password=password, is_ssl=is_ssl, ssl_ctx=ssl_ctx, certpath=certpath
        )
        self.host = host
        self.port = port

    async def connect(self, protocol_factory, *, loop=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()

        return await loop.create_connection(
            protocol_factory, self.host, self.port, **kwargs
        )

    def __str__(self) -> str:
        if self.is_ssl:
            return "{}:+{}".format(self.host, self.port)

        return "{}:{}".format(self.host, self.port)


class BasicUNIXServer(BaseServer):
    def __init__(
        self,
        *,
        path: str,
        is_ssl: bool = False,
        password: str = None,
        ssl_ctx: ssl.SSLContext = None,
        certpath: str = None,
    ) -> None:
        super().__init__(
            is_ssl=is_ssl, password=password, ssl_ctx=ssl_ctx, certpath=certpath
        )
        self.path = path

    async def connect(self, protocol_factory, *, loop=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()

        return await loop.create_unix_connection(protocol_factory, self.path, **kwargs)

    def __str__(self) -> str:
        if self.is_ssl:
            return "{} (ssl)".format(self.path)

        return self.path


class Server(BasicIPServer):
    """Represents a server to connect to"""

    def __init__(
        self, host: str, port: int, is_ssl: bool = False, password: str = None
    ):
        super().__init__(host=host, port=port, is_ssl=is_ssl, password=password)


class BadAttribute(AttributeError):
    def __init__(self, obj, attr):
        super().__init__(
            "Incorrect base connection type ({} has no attribute {!r})".format(
                type(obj).__name__, attr
            )
        )


class ConnectedServer:
    """Represents a connected server

    Used to store session data like ISUPPORT tokens and enabled CAPs
    """

    last_ping_sent = -1
    last_ping_recv = -1
    lag = -1

    def __init__(self, server: 'BaseServer') -> None:
        self.connection = server
        self.is_ssl = server.is_ssl
        self.password = server.password
        self.isupport_tokens: Dict[str, str] = {}
        self.caps: Dict[str, Tuple[Cap, Optional[bool]]] = {}
        self.server_name = None
        self.data = {}

    @property
    def host(self):
        try:
            return self.connection.host
        except AttributeError as e:
            raise BadAttribute(self.connection, e.args[0])

    @property
    def port(self):
        try:
            return self.connection.port
        except AttributeError as e:
            raise BadAttribute(self.connection, e.args[0])
