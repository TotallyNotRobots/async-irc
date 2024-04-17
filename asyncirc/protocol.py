"""Basic asyncio.Protocol interface for IRC connections."""

import asyncio
import base64
import random
import socket
import time
from asyncio import Protocol, Task
from collections import defaultdict
from enum import IntEnum, auto, unique
from itertools import cycle
from typing import (
    TYPE_CHECKING,
    Callable,
    Coroutine,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
)

from irclib.parser import Cap, CapList, Message

from asyncirc.server import ConnectedServer
from asyncirc.util.backoff import AsyncDelayer

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop, Transport
    from logging import Logger

    from asyncirc.server import BaseServer


__all__ = ("SASLMechanism", "IrcProtocol")


@unique
class SASLMechanism(IntEnum):
    """Represents different SASL auth mechanisms."""

    NONE = auto()
    PLAIN = auto()
    EXTERNAL = auto()


async def _internal_ping(conn: "IrcProtocol", message: "Message") -> None:
    conn.send(f"PONG {message.parameters}")


def _handle_cap_list(conn: "IrcProtocol", caplist: "List[Cap]") -> None:
    if conn.logger:
        conn.logger.info("Current Capabilities: %s", caplist)


def _handle_cap_del(
    conn: "IrcProtocol", caplist: "List[Cap]", server: "ConnectedServer"
) -> None:
    if conn.logger:
        conn.logger.info("Capabilities removed: %s", caplist)

    for cap in caplist:
        current = server.caps[cap.name][0]
        server.caps[cap.name] = (current, False)


def _handle_cap_new(
    conn: "IrcProtocol",
    message: "Message",
    caplist: "List[Cap]",
    server: "ConnectedServer",
) -> None:
    if conn.logger:
        conn.logger.info("New capabilities advertised: %s", caplist)

    for cap in caplist:
        if cap.name in conn.cap_handlers:
            server.caps[cap.name] = (cap, None)

    if message.parameters[2] != "*":
        for cap_name in server.caps:
            conn.send(f"CAP REQ :{cap_name}")


async def _handle_cap_reply(
    conn: "IrcProtocol",
    message: "Message",
    caplist: "List[Cap]",
    server: "ConnectedServer",
) -> None:
    enabled = message.parameters[1] == "ACK"
    for cap in caplist:
        current = server.caps[cap.name][0]
        if enabled:
            handlers = filter(None, conn.cap_handlers[cap.name])
            await asyncio.gather(*[func(conn, cap) for func in handlers])

        server.caps[cap.name] = (current, enabled)

    if all(val[1] is not None for val in server.caps.values()):
        conn.send("CAP END")


def _handle_cap_ls(
    conn: "IrcProtocol",
    message: "Message",
    caplist: "List[Cap]",
    server: "ConnectedServer",
) -> None:
    for cap in caplist:
        if cap.name in conn.cap_handlers:
            server.caps[cap.name] = (cap, None)

    if message.parameters[2] != "*":
        for cap_name in server.caps:
            conn.send(f"CAP REQ :{cap_name}")

        if not server.caps:
            # We haven't requested any CAPs, send a CAP END to end negotiation
            conn.send("CAP END")


async def _internal_cap_handler(
    conn: "IrcProtocol", message: "Message"
) -> None:
    if conn.server is None:
        msg = "Server not set in handler"
        raise ValueError(msg)

    caplist: List[Cap] = []
    if len(message.parameters) > 2:
        caplist = CapList.parse(message.parameters[-1])

    if message.parameters[1] == "LS":
        _handle_cap_ls(conn, message, caplist, conn.server)
    elif message.parameters[1] in ("ACK", "NAK"):
        await _handle_cap_reply(conn, message, caplist, conn.server)
    elif message.parameters[1] == "LIST":
        _handle_cap_list(conn, caplist)
    elif message.parameters[1] == "NEW":
        _handle_cap_new(conn, message, caplist, conn.server)
    elif message.parameters[1] == "DEL":
        _handle_cap_del(conn, caplist, conn.server)


async def _internal_pong(conn: "IrcProtocol", msg: "Message") -> None:
    if conn.server is None:
        err_msg = "Server not set in handler"
        raise ValueError(err_msg)

    if msg.parameters[-1].startswith("LAG"):
        now = time.time()
        t = float(msg.parameters[-1][3:])
        if conn.server.last_ping_sent == t:
            conn.server.last_ping_recv = now
            conn.server.lag = now - t


async def _do_sasl(conn: "IrcProtocol", cap: Cap) -> None:
    if conn.server is None:
        msg = "Server not set in handler"
        raise ValueError(msg)

    if not conn.sasl_mech or conn.sasl_mech is SASLMechanism.NONE:
        return

    if cap.value is not None:
        supported_mechs: Optional[List[str]] = cap.value.split(",")
    else:
        supported_mechs = None

    if supported_mechs and conn.sasl_mech.name not in supported_mechs:
        if conn.logger:
            conn.logger.warning(
                "Server doesn't support configured SASL mechanism '%s'",
                conn.sasl_mech,
            )

        return

    conn.send(f"AUTHENTICATE {conn.sasl_mech.name}")
    auth_msg = await conn.wait_for("AUTHENTICATE", timeout=5)
    if auth_msg and auth_msg.parameters[0] == "+":
        auth_line = "+"
        if conn.sasl_mech == SASLMechanism.PLAIN:
            if conn.sasl_auth is None:
                msg = "You must specify sasl_auth when using SASL PLAIN"
                raise ValueError(msg)

            user, password = conn.sasl_auth
            auth_line = f"{user}\x00{user}\x00{password}"
            auth_line = base64.b64encode(auth_line.encode()).decode()

        conn.send(f"AUTHENTICATE {auth_line}")
        # Wait for SASL to complete
        # TODO(linuxdaemon): log SASL response
        await conn.wait_for(
            "902", "903", "904", "905", "906", "907", "908", timeout=30
        )


async def _isupport_handler(conn: "IrcProtocol", message: "Message") -> None:
    if conn.server is None:
        msg = "Server not set in handler"
        raise ValueError(msg)

    # Remove the nick and trailing ':are supported by this server' message
    tokens = message.parameters[1:-1]
    for token in tokens:
        if token[0] == "-" and token.upper() in conn.server.isupport_tokens:
            del conn.server.isupport_tokens[token.upper()]
        else:
            name, _, value = token.partition("=")
            conn.server.isupport_tokens[name.upper()] = value or None


async def _on_001(conn: "IrcProtocol", message: "Message") -> None:
    if conn.server is None:
        msg = "Server not set in handler"
        raise ValueError(msg)

    if not message.prefix:
        msg = f"Missing prefix in 001: {message}"
        raise ValueError(msg)

    conn.server.server_name = message.prefix.mask


class IrcProtocol(Protocol):
    """Async IRC Interface."""

    _transport: Optional["Transport"] = None
    _buff = b""
    _server: Optional["ConnectedServer"] = None
    _connected = False
    _quitting = False

    def __init__(
        self,
        servers: Sequence["BaseServer"],
        nick: str,
        user: Optional[str] = None,
        realname: Optional[str] = None,
        certpath: Optional[str] = None,
        sasl_auth: Optional[Tuple[str, str]] = None,
        sasl_mech: Optional[SASLMechanism] = None,
        logger: Optional["Logger"] = None,
        loop: Optional["AbstractEventLoop"] = None,
    ) -> None:
        """Create protocol for IRC connection.

        Args:
            servers: List of server configurations to use
            nick: nickname to use
            user: username/ident to use. Defaults to `nick`.
            realname: realname/GECOS to use. Defaults to `nick`.
            certpath: Path to client certificate. Defaults to None.
            sasl_auth: Auth configuration for SASL PLAIN, format (`username`, `password`). \
                Defaults to None.
            sasl_mech: SASL mechanism to use, e.g. SaslMechanism.PLAIN. Defaults to None.
            logger: Logger to use. Defaults to None.
            loop: Asyncio loop to run with. Defaults to None.

        Raises:
            ValueError: If sasl_auth is not set but sasl_mechanism is set to PLAIN.
        """
        self.servers = servers
        self.nick = nick
        self._user = user
        self._realname = realname
        self.certpath = certpath
        self.sasl_auth = sasl_auth
        self.sasl_mech = SASLMechanism(sasl_mech or SASLMechanism.NONE)
        self.logger = logger
        self.loop = loop or asyncio.get_event_loop()

        if self.sasl_mech == SASLMechanism.PLAIN and self.sasl_auth is None:
            msg = "You must specify sasl_auth when using SASL PLAIN"
            raise ValueError(msg)

        self.handlers: Dict[
            int,
            Tuple[
                str,
                Callable[
                    ["IrcProtocol", "Message"], Coroutine[None, None, None]
                ],
            ],
        ] = {}
        self.cap_handlers: Dict[
            str,
            List[
                Optional[
                    Callable[
                        ["IrcProtocol", "Cap"], Coroutine[None, None, None]
                    ]
                ]
            ],
        ] = defaultdict(list)

        self._connected_future = self.loop.create_future()
        self.quit_future = self.loop.create_future()

        self.register("PING", _internal_ping)
        self.register("PONG", _internal_pong)
        self.register("CAP", _internal_cap_handler)
        self.register("001", _on_001)
        self.register("005", _isupport_handler)
        self.register_cap("sasl", _do_sasl)

        self._pinger: Optional[Task[None]] = self.loop.create_task(
            self.pinger()
        )

    def __del__(self) -> None:
        """Automatically close connection on garbage collection."""
        self.close()

    async def pinger(self) -> None:
        """Continuous task to ping server and check current lag.

        Autoreconnects if lag exceeds `self.max_lag`.

        Raises:
            ValueError:
                If `self.server` is None when `self.connected` is True (which should not happen).
        """
        while True:
            if self.connected:
                if self.server is None:
                    msg = "Server not set in ping handler"
                    raise ValueError(msg)

                if self.server.lag > 60:
                    self.loop.create_task(self.connect())
                else:
                    self.send(f"PING :LAG{time.time()}")

            await asyncio.sleep(30)

    def close(self) -> None:
        """Close connection and background tasks."""
        if (
            self._pinger
            and self._pinger.get_loop().is_running()
            and not self._pinger.done()
        ):
            self._pinger.cancel()
            self._pinger = None

    async def _connect(self, server: "BaseServer") -> bool:
        self._connected_future = self.loop.create_future()
        self.quit_future = self.loop.create_future()
        self._server = ConnectedServer(server)
        if self.logger:
            if self.connected:
                self.logger.info("Reconnecting to %s", self.server)
            else:
                self.logger.info("Connecting to %s", self.server)

        fut = self._server.connection.do_connect(self)
        try:
            await asyncio.wait_for(fut, 30)
        except asyncio.TimeoutError:
            if self.logger:
                self.logger.exception(
                    "Connection timeout occurred while connecting to %s",
                    self.server,
                )

            return False
        except (ConnectionError, socket.gaierror):
            if self.logger:
                self.logger.exception(
                    "Error occurred while connecting to %s", self.server
                )

            return False

        return True

    async def connect(self) -> None:
        """Attempt to connect to the server, cycling through the server list until successful."""
        delayer = AsyncDelayer(2)
        for server in cycle(self.servers):
            async with delayer:
                if await self._connect(server):
                    break

    def register(
        self,
        cmd: str,
        handler: Callable[
            ["IrcProtocol", "Message"], Coroutine[None, None, None]
        ],
    ) -> int:
        """Register a command handler."""
        hook_id = 0
        while not hook_id or hook_id in self.handlers:
            hook_id = random.randint(1, (2**32) - 1)

        self.handlers[hook_id] = (cmd, handler)
        return hook_id

    def unregister(self, hook_id: int) -> None:
        """Unregister a hook."""
        del self.handlers[hook_id]

    def register_cap(
        self,
        cap: str,
        handler: Optional[
            Callable[["IrcProtocol", "Cap"], Coroutine[None, None, None]]
        ] = None,
    ) -> None:
        """Register a CAP handler.

        If the handler is None, the CAP will be requested from the server,
        but no handler will be called, allowing registration of CAPs that
        only require basic requests
        """
        self.cap_handlers[cap].append(handler)

    async def wait_for(
        self, *cmds: str, timeout: Optional[int] = None
    ) -> Optional[Message]:
        """Wait for a matching command from the server.

        Wait for a specific command from the server, optionally returning after [timeout] seconds.
        """
        if not cmds:
            return None

        fut: "asyncio.Future[Message]" = self.loop.create_future()

        async def _wait(_conn: "IrcProtocol", message: "Message") -> None:
            if not fut.done():
                fut.set_result(message)

        hooks = [self.register(cmd, _wait) for cmd in cmds]

        try:
            result = await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            result = None
        finally:
            for hook_id in hooks:
                self.unregister(hook_id)

        return result

    async def _send(self, text: Union[str, bytes]) -> None:
        if not self.connected:
            await self._connected_future

        if isinstance(text, str):
            text = text.encode()
        elif isinstance(text, memoryview):
            text = text.tobytes()

        if self.logger:
            self.logger.info(">> %s", text.decode())

        if self._transport is None:
            msg = "Can't send to missing transport"
            raise ValueError(msg)

        self._transport.write(text + b"\r\n")

    def send(self, text: Union[str, bytes]) -> None:
        """Send a raw line to the server."""
        asyncio.run_coroutine_threadsafe(self._send(text), self.loop)

    def send_command(self, msg: Message) -> None:
        """Send an irclib Message object to the server."""
        return self.send(str(msg))

    def quit(self, reason: Optional[str] = None) -> None:
        """Quit the IRC connection with an optional reason."""
        if not self._quitting:
            self._quitting = True
            if reason:
                self.send(f"QUIT {reason}")
            else:
                self.send("QUIT")

    def connection_made(self, transport: "asyncio.BaseTransport") -> None:
        """Called by the event loop when the connection has been established."""
        if not self.server:
            msg = "Server not set during connection_made()"
            raise ValueError(msg)

        self._transport = cast(asyncio.Transport, transport)
        self._connected = True
        self._connected_future.set_result(None)
        del self._connected_future
        self.send("CAP LS 302")
        if self.server.password:
            self.send(f"PASS {self.server.password}")

        self.send(f"NICK {self.nick}")
        self.send(f"USER {self.user} 0 * :{self.realname}")

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Connection to the IRC server has been lost."""
        self._transport = None
        self._connected = False
        if not self._quitting:
            if self.logger and exc:
                self.logger.error(
                    "Error occurred in connection to %s",
                    self.server,
                    exc_info=exc,
                )

            self._connected_future = self.loop.create_future()
            asyncio.run_coroutine_threadsafe(self.connect(), self.loop)
        else:
            self.quit_future.set_result(None)

    def data_received(self, data: bytes) -> None:
        """Called by the event loop when data has been read from the socket."""
        self._buff += data
        while b"\r\n" in self._buff:
            raw_line, self._buff = self._buff.split(b"\r\n", 1)
            message = Message.parse(raw_line)
            for trigger, func in self.handlers.values():
                if trigger in (message.command, "*"):
                    self.loop.create_task(func(self, message))

    @property
    def user(self) -> str:
        """The username used for this connection."""
        return self._user or self.nick

    @user.setter
    def user(self, value: str) -> None:
        self._user = value

    @property
    def realname(self) -> str:
        """The realname or GECOS used for this connection."""
        return self._realname or self.nick

    @realname.setter
    def realname(self, value: str) -> None:
        self._realname = value

    @property
    def connected(self) -> bool:
        """Whether or not the connection is still active."""
        return self._connected

    @property
    def server(self) -> Optional["ConnectedServer"]:
        """The current server object."""
        return self._server

    def __call__(self) -> "IrcProtocol":
        """Returns self.

        This is here to allow an instance of IrcProtocol to be
        passed directly to loop.create_connection().
        """
        return self

    def __enter__(self) -> "IrcProtocol":
        """Begin connection context."""
        return self

    def __exit__(self, *exc: object) -> None:
        """Finish connection context.

        If the connection is still active, this will send a QUIT to the server.
        """
        if self.connected:
            self.quit()

        self.close()

    async def __aenter__(self) -> "IrcProtocol":
        """Begin connection context."""
        return self.__enter__()

    async def __aexit__(self, *exc: object) -> None:
        """Finish connection context.

        If the connection is still active, this will send a QUIT to the server
        and wait until the quit has completed.
        """
        if self.connected:
            self.quit()
            await self.quit_future

        self.close()
