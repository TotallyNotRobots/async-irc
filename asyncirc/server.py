"""Server objects used for different stages in the connect process to store contextual data."""

import asyncio
import ssl
import warnings
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

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
    """Abstract server specification to store connect information and session data."""

    def __init__(
        self,
        *,
        password: str | None = None,
        is_ssl: bool = False,
        ssl_ctx: ssl.SSLContext | None = None,
        certpath: str | None = None,
    ) -> None:
        """Set server connection options.

        Args:
            password: Server password to use. Defaults to None.
            is_ssl: Whether to use TLS. Defaults to False.
            ssl_ctx: Optional SSLContext to use. Defaults to None.
            certpath: Client cert path to read. Defaults to None.
        """
        if is_ssl:
            if ssl_ctx is None:
                ssl_ctx = ssl.create_default_context()

            if certpath:
                ssl_ctx.load_cert_chain(certpath)

            self.ssl_ctx: ssl.SSLContext | None = ssl_ctx
        else:
            self.ssl_ctx = None

        self.password = password

    @property
    def is_ssl(self) -> bool:
        """Whether this connection uses TLS."""
        return self.ssl_ctx is not None

    async def connect(
        self,
        protocol_factory: Callable[[], _ProtoT],
        *,
        loop: asyncio.AbstractEventLoop | None = None,
        ssl: ssl.SSLContext | None = None,
    ) -> tuple[asyncio.Transport, _ProtoT]:
        """Internal connect implementation.

        This should not be called outside of `BaseServer`.

        Args:
            protocol_factory: Factory function that returns an `asyncio.Protocol` implementation.
            loop: Asyncio event loop to use. Defaults to None.
            ssl: SSLContext to use. Defaults to None.

        Returns:
            Tuple of the created `asyncio.Transport`
            and the protocol returned from `protocol_factory`.
        """
        raise NotImplementedError

    async def do_connect(
        self,
        protocol_factory: Callable[[], _ProtoT],
        *,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> tuple[asyncio.Transport, _ProtoT]:
        """Wrapper for internal connect implementation.

        Args:
            protocol_factory: Factory that returns a asyncio.Protocol implementation.
            loop: Asyncio loop to use. Defaults to None.

        Returns:
            Tuple of transport and protocol.
        """
        return await self.connect(protocol_factory, loop=loop, ssl=self.ssl_ctx)

    def __str__(self) -> str:
        """Describe server configuration."""
        raise NotImplementedError


class BasicIPServer(BaseServer):
    """A simple implementation for connecting to a normal TCP server."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        is_ssl: bool = False,
        password: str | None = None,
        ssl_ctx: ssl.SSLContext | None = None,
        certpath: str | None = None,
    ) -> None:
        """Create TCP server configuration.

        Args:
            host: Hostname
            port: Port
            is_ssl: Whether to use TLS. Defaults to False.
            password: Server password. Defaults to None.
            ssl_ctx: SSLContext to use. Defaults to None.
            certpath: Path to client cert to use. Defaults to None.
        """
        super().__init__(
            password=password, is_ssl=is_ssl, ssl_ctx=ssl_ctx, certpath=certpath
        )

        self.host = host
        self.port = port

    async def connect(
        self,
        protocol_factory: Callable[[], _ProtoT],
        *,
        loop: asyncio.AbstractEventLoop | None = None,
        ssl: ssl.SSLContext | None = None,
    ) -> tuple[asyncio.Transport, _ProtoT]:
        """TCP server connection implementation.

        Args:
            protocol_factory: Factory to return asyncio.Protocol to use.
            loop: Asyncio loop to use. Defaults to None.
            ssl: SSLContext to use. Defaults to None.

        Returns:
            Tuple of transport and protocol
        """
        if loop is None:
            loop = asyncio.get_event_loop()

        return await loop.create_connection(
            protocol_factory, self.host, self.port, ssl=ssl
        )

    def __str__(self) -> str:
        """Describe TCP server configuration."""
        if self.is_ssl:
            return f"{self.host}:+{self.port}"

        return f"{self.host}:{self.port}"


class BasicUNIXServer(BaseServer):
    """Server implementation for unix-socket based connections."""

    def __init__(
        self,
        *,
        path: str,
        is_ssl: bool = False,
        password: str | None = None,
        ssl_ctx: ssl.SSLContext | None = None,
        certpath: str | None = None,
    ) -> None:
        """Configure UNIX socket based server connection.

        Args:
            path: Path to socket.
            is_ssl: Whether to use TLS. Defaults to False.
            password: Server password. Defaults to None.
            ssl_ctx: SSLContext to use. Defaults to None.
            certpath: Path to client cert to use. Defaults to None.
        """
        super().__init__(
            is_ssl=is_ssl, password=password, ssl_ctx=ssl_ctx, certpath=certpath
        )

        self.path = path

    async def connect(
        self,
        protocol_factory: Callable[[], _ProtoT],
        *,
        loop: asyncio.AbstractEventLoop | None = None,
        ssl: ssl.SSLContext | None = None,
    ) -> tuple[asyncio.Transport, _ProtoT]:
        """Connect to UNIX socket.

        Args:
            protocol_factory: Factory which returns an asyncio.Protocol implementation.
            loop: Asyncio loop to use. Defaults to None.
            ssl: SSLContext to use. Defaults to None.

        Returns:
            Tuple of transport and protocol.
        """
        if loop is None:
            loop = asyncio.get_event_loop()

        return await loop.create_unix_connection(
            protocol_factory, self.path, ssl=ssl
        )

    def __str__(self) -> str:
        """Describe UNIX socket connection."""
        if self.is_ssl:
            return f"{self.path} (ssl)"

        return self.path


class Server(BasicIPServer):
    """Represents a server to connect to."""

    def __init__(
        self,
        host: str,
        port: int,
        is_ssl: bool = False,
        password: str | None = None,
    ) -> None:
        """Create basic server configuration.

        This is deprecated in favor of BasicIPServer().

        Args:
            host: Server hostname
            port: Server port
            is_ssl: Whetner to use TLS. Defaults to False.
            password: Server password. Defaults to None.
        """
        warnings.warn(
            "Server() is deprecated in favor of BasicIPServer()",
            DeprecationWarning,
            stacklevel=1,
        )
        super().__init__(host=host, port=port, is_ssl=is_ssl, password=password)


class ConnectedServer:
    """Represents a connected server.

    Used to store session data like ISUPPORT tokens and enabled CAPs
    """

    last_ping_sent: float = -1
    last_ping_recv: float = -1
    lag: float = -1

    def __init__(self, server: "BaseServer") -> None:
        """Create session data.

        Args:
            server: Server connection configuration
        """
        self.connection = server
        self.is_ssl = server.is_ssl
        self.password = server.password
        self.isupport_tokens: dict[str, str | None] = {}
        self.caps: dict[str, tuple[Cap, bool | None]] = {}
        self.server_name: str | None = None
        self.data: dict[str, Any] = {}
