"""
Server objects used for different stages in the connect process
to store contextual data
"""

import asyncio
import ssl
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple, TypeVar

if TYPE_CHECKING:
    from irclib.parser import Cap

__all__ = (
    "BaseServer",
    "Server",
    "BasicIPServer",
    "BasicUNIXServer",
    "ConnectedServer",
)

_ProtoT = TypeVar("_ProtoT", bound=asyncio.Protocol)


class BaseServer:
    def __init__(
        self,
        *,
        password: Optional[str] = None,
        is_ssl: bool = False,
        ssl_ctx: Optional[ssl.SSLContext] = None,
        certpath: Optional[str] = None,
    ) -> None:
        if is_ssl:
            if ssl_ctx is None:
                ssl_ctx = ssl.create_default_context()

            if certpath:
                ssl_ctx.load_cert_chain(certpath)

            self.ssl_ctx: Optional[ssl.SSLContext] = ssl_ctx
        else:
            self.ssl_ctx = None

        self.password = password

    @property
    def is_ssl(self) -> bool:
        return self.ssl_ctx is not None

    async def connect(
        self,
        protocol_factory: Callable[[], _ProtoT],
        *,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        **kwargs: Any,
    ) -> Tuple[asyncio.Transport, _ProtoT]:
        raise NotImplementedError

    async def do_connect(
        self,
        protocol_factory: Callable[[], _ProtoT],
        *,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> Tuple[asyncio.Transport, _ProtoT]:
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
        password: Optional[str] = None,
        ssl_ctx: Optional[ssl.SSLContext] = None,
        certpath: Optional[str] = None,
    ) -> None:
        super().__init__(
            password=password, is_ssl=is_ssl, ssl_ctx=ssl_ctx, certpath=certpath
        )

        self.host = host
        self.port = port

    async def connect(
        self,
        protocol_factory: Callable[[], _ProtoT],
        *,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        **kwargs: Any,
    ) -> Tuple[asyncio.Transport, _ProtoT]:
        if loop is None:
            loop = asyncio.get_event_loop()

        return await loop.create_connection(
            protocol_factory, self.host, self.port, **kwargs
        )

    def __str__(self) -> str:
        if self.is_ssl:
            return f"{self.host}:+{self.port}"

        return f"{self.host}:{self.port}"


class BasicUNIXServer(BaseServer):
    def __init__(
        self,
        *,
        path: str,
        is_ssl: bool = False,
        password: Optional[str] = None,
        ssl_ctx: Optional[ssl.SSLContext] = None,
        certpath: Optional[str] = None,
    ) -> None:
        super().__init__(
            is_ssl=is_ssl, password=password, ssl_ctx=ssl_ctx, certpath=certpath
        )
        self.path = path

    async def connect(
        self,
        protocol_factory: Callable[[], _ProtoT],
        *,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        **kwargs: Any,
    ) -> Tuple[asyncio.Transport, _ProtoT]:
        if loop is None:
            loop = asyncio.get_event_loop()

        return await loop.create_unix_connection(
            protocol_factory, self.path, **kwargs
        )

    def __str__(self) -> str:
        if self.is_ssl:
            return f"{self.path} (ssl)"

        return self.path


class Server(BasicIPServer):
    """Represents a server to connect to"""

    def __init__(
        self,
        host: str,
        port: int,
        is_ssl: bool = False,
        password: Optional[str] = None,
    ) -> None:
        super().__init__(host=host, port=port, is_ssl=is_ssl, password=password)


class ConnectedServer:
    """Represents a connected server

    Used to store session data like ISUPPORT tokens and enabled CAPs
    """

    last_ping_sent: float = -1
    last_ping_recv: float = -1
    lag: float = -1

    def __init__(self, server: "BaseServer") -> None:
        self.connection = server
        self.is_ssl = server.is_ssl
        self.password = server.password
        self.isupport_tokens: Dict[str, Optional[str]] = {}
        self.caps: Dict[str, Tuple[Cap, Optional[bool]]] = {}
        self.server_name: Optional[str] = None
        self.data: Dict[str, Any] = {}
