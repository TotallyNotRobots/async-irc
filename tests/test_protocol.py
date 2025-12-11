# SPDX-FileCopyrightText: 2017-2020 Snoonet
# SPDX-FileCopyrightText: 2020-present linuxdaemon <linuxdaemon.irc@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Test protocol implementations."""

import asyncio
import logging
import ssl
from collections.abc import Callable, Mapping
from ssl import SSLContext
from typing import Any, TypeVar

from irclib.parser import Message

from asyncirc.protocol import IrcProtocol, SASLMechanism
from asyncirc.server import BaseServer


class MockTransport(asyncio.Transport):
    """Mock transport implementation."""

    def __init__(
        self,
        server: "MockServer",
        protocol: asyncio.BaseProtocol,
        extra: Mapping[str, Any] | None = None,
        sasl_cap_mechs: list[str] | None = None,
    ) -> None:
        """Create mock transport for testing.

        Args:
            server: Server configuration.
            protocol: protocol implementation.
            loop: Asyncio loop to use.
            ssl: SSLContext to use.
            extra: Extra transport data. Defaults to None.
        """
        super().__init__(extra)
        self._server = server
        if not isinstance(protocol, IrcProtocol):  # pragma: no cover
            msg = f"Protocol is wrong type: {type(protocol)}"
            raise TypeError(msg)

        self._protocol = protocol
        self._write_buffer = b""

        self._received_user = False
        self._received_cap_ls = False
        self._received_nick = False
        self._received_cap_end = False
        self._did_ping = False
        self._registered = False
        self._sasl_cap_mechs = sasl_cap_mechs

    def write(self, data: bytes | bytearray | memoryview) -> None:
        """'Write data to the server.

        This just handles the incoming data and sends responses directly to the Protocol.

        Args:
            data: Data to send
        """
        assert self._protocol.logger is not None
        self._protocol.logger.info(data)

        self._write_buffer += data
        while b"\r\n" in self._write_buffer:
            part, self._write_buffer = self._write_buffer.split(b"\r\n", 1)
            msg = Message.parse(part)
            self._server.lines.append(("in", str(msg)))
            if msg.command == "CAP" and msg.parameters[0] == "LS":
                self._received_cap_ls = True
                if self._sasl_cap_mechs:
                    sasl_cap = f"sasl={','.join(self._sasl_cap_mechs)}"
                else:
                    sasl_cap = "sasl"

                self._server.send_line(
                    Message.parse(
                        f":irc.example.com CAP * LS :foo {sasl_cap} bar"
                    )
                )
            elif msg.command == "USER":
                self._received_user = True
            elif msg.command == "NICK":
                self._received_nick = True
            elif msg.command == "CAP" and msg.parameters[0] == "END":
                self._received_cap_end = True
            elif msg.command == "CAP" and msg.parameters[0] == "REQ":
                self._server.send_line(
                    Message.parse(
                        f":irc.example.com CAP * ACK :{msg.parameters[1]}"
                    )
                )
            elif msg.command == "AUTHENTICATE" and msg.parameters[0] == "PLAIN":
                self._server.send_line(
                    Message.parse(":irc.example.com AUTHENTICATE +")
                )
            elif msg.command == "AUTHENTICATE":
                self._server.send_line(Message.parse(":irc.example.com 903"))
            elif msg.command == "QUIT":
                self._protocol.connection_lost(None)
            elif msg.command == "PONG":
                self._did_ping = True

            if not self._registered and (
                self._received_nick
                and self._received_user
                and (not self._received_cap_ls or self._received_cap_end)
            ):
                if self._did_ping:
                    self._registered = True
                    self._server.send_line(
                        Message.parse(":irc.example.com 001")
                    )
                else:
                    self._server.send_line(
                        Message.parse(":irc.example.com PING foobar")
                    )

    def get_protocol(self) -> IrcProtocol:
        """Get current protocol."""
        return self._protocol


_ProtoT = TypeVar("_ProtoT", bound=asyncio.Protocol)


class MockServer(BaseServer):
    """Mock server implementation for testing."""

    def __init__(
        self,
        *,
        password: str | None = None,
        is_ssl: bool = False,
        ssl_ctx: SSLContext | None = None,
        certpath: str | None = None,
        sasl_cap_mechs: list[str] | None = None,
    ) -> None:
        """Configure mock server.

        Args:
            password: Server password. Defaults to None.
            is_ssl: Whether to use TLS. Defaults to False.
            ssl_ctx: SSLContext to use. Defaults to None.
            certpath: Path to client cert to use. Defaults to None.
        """
        super().__init__(
            password=password, is_ssl=is_ssl, ssl_ctx=ssl_ctx, certpath=certpath
        )
        self.lines: list[tuple[str, str]] = []
        self.in_buffer = b""
        self.transport: MockTransport | None = None
        self.sasl_cap_mechs = sasl_cap_mechs

    def send_line(self, msg: Message) -> None:
        """Send line back to client.

        Args:
            msg: Message to send to client.
        """
        assert self.transport is not None
        self.lines.append(("out", str(msg)))
        self.transport.get_protocol().data_received(str(msg).encode() + b"\r\n")

    async def connect(
        self,
        protocol_factory: Callable[[], _ProtoT],
        *,
        loop: asyncio.AbstractEventLoop | None = None,
        ssl: ssl.SSLContext | None = None,
    ) -> tuple[asyncio.Transport, _ProtoT]:
        """Mock connection implementation.

        Args:
            protocol_factory: Factory for mock protocol.
            loop: Asyncio loop to use. Defaults to None.
            ssl: SSLContext to use. Defaults to None.

        Returns:
            Tuple of transport and protocol.
        """
        proto = protocol_factory()
        self.transport = MockTransport(
            self, proto, sasl_cap_mechs=self.sasl_cap_mechs
        )
        proto.connection_made(self.transport)
        return self.transport, proto


async def test_sasl() -> None:
    """Test sasl flow."""
    fut = asyncio.Future[None]()

    async def _on_001(_conn: IrcProtocol, _msg: Message) -> None:
        _conn.send_command(Message.parse("PRIVMSG #foo :bar"))
        fut.set_result(None)

    server = MockServer()

    logging.getLogger("asyncio").setLevel(0)

    with IrcProtocol(
        [server],
        "nick",
        sasl_auth=("foo", "bar"),
        sasl_mech=SASLMechanism.PLAIN,
        logger=logging.getLogger("asyncirc"),
    ) as proto:
        proto.register_cap("foo")
        proto.register_cap("bar")
        proto.register("001", _on_001)
        await proto.connect()
        await fut
        proto.quit()
        await proto.quit_future

    assert server.lines == [
        (
            "in",
            "CAP LS 302",
        ),
        (
            "out",
            ":irc.example.com CAP * LS :foo sasl bar",
        ),
        (
            "in",
            "NICK nick",
        ),
        (
            "in",
            "USER nick 0 * :nick",
        ),
        (
            "in",
            "CAP REQ :foo",
        ),
        (
            "out",
            ":irc.example.com CAP * ACK :foo",
        ),
        (
            "in",
            "CAP REQ :sasl",
        ),
        (
            "out",
            ":irc.example.com CAP * ACK :sasl",
        ),
        (
            "in",
            "CAP REQ :bar",
        ),
        (
            "out",
            ":irc.example.com CAP * ACK :bar",
        ),
        (
            "in",
            "AUTHENTICATE PLAIN",
        ),
        (
            "out",
            ":irc.example.com AUTHENTICATE +",
        ),
        (
            "in",
            "AUTHENTICATE Zm9vAGZvbwBiYXI=",
        ),
        (
            "out",
            ":irc.example.com 903",
        ),
        (
            "in",
            "CAP END",
        ),
        (
            "out",
            ":irc.example.com PING foobar",
        ),
        ("in", "PONG foobar"),
        (
            "out",
            ":irc.example.com 001",
        ),
        ("in", "PRIVMSG #foo :bar"),
        (
            "in",
            "QUIT",
        ),
    ]


async def test_sasl_multiple_mechs() -> None:
    """Test sasl flow."""
    fut = asyncio.Future[None]()

    async def _on_001(_conn: IrcProtocol, _msg: Message) -> None:
        _conn.send_command(Message.parse("PRIVMSG #foo :bar"))
        fut.set_result(None)

    server = MockServer(sasl_cap_mechs=["PLAIN", "EXTERNAL"])

    logging.getLogger("asyncio").setLevel(0)

    with IrcProtocol(
        [server],
        "nick",
        sasl_auth=("foo", "bar"),
        sasl_mech=SASLMechanism.PLAIN,
        logger=logging.getLogger("asyncirc"),
    ) as proto:
        proto.register_cap("foo")
        proto.register_cap("bar")
        proto.register("001", _on_001)
        await proto.connect()
        await fut
        proto.quit()
        await proto.quit_future

    assert server.lines == [
        (
            "in",
            "CAP LS 302",
        ),
        (
            "out",
            ":irc.example.com CAP * LS :foo sasl=PLAIN,EXTERNAL bar",
        ),
        (
            "in",
            "NICK nick",
        ),
        (
            "in",
            "USER nick 0 * :nick",
        ),
        (
            "in",
            "CAP REQ :foo",
        ),
        (
            "out",
            ":irc.example.com CAP * ACK :foo",
        ),
        (
            "in",
            "CAP REQ :sasl",
        ),
        (
            "out",
            ":irc.example.com CAP * ACK :sasl",
        ),
        (
            "in",
            "CAP REQ :bar",
        ),
        (
            "out",
            ":irc.example.com CAP * ACK :bar",
        ),
        (
            "in",
            "AUTHENTICATE PLAIN",
        ),
        (
            "out",
            ":irc.example.com AUTHENTICATE +",
        ),
        (
            "in",
            "AUTHENTICATE Zm9vAGZvbwBiYXI=",
        ),
        (
            "out",
            ":irc.example.com 903",
        ),
        (
            "in",
            "CAP END",
        ),
        (
            "out",
            ":irc.example.com PING foobar",
        ),
        ("in", "PONG foobar"),
        (
            "out",
            ":irc.example.com 001",
        ),
        ("in", "PRIVMSG #foo :bar"),
        (
            "in",
            "QUIT",
        ),
    ]


async def test_sasl_unsupported_mechs() -> None:
    """Test sasl flow."""
    fut = asyncio.Future[None]()

    async def _on_001(_conn: IrcProtocol, _msg: Message) -> None:
        _conn.send_command(Message.parse("PRIVMSG #foo :bar"))
        fut.set_result(None)

    server = MockServer(sasl_cap_mechs=["EXTERNAL"])

    logging.getLogger("asyncio").setLevel(0)

    with IrcProtocol(
        [server],
        "nick",
        sasl_auth=("foo", "bar"),
        sasl_mech=SASLMechanism.PLAIN,
        logger=logging.getLogger("asyncirc"),
    ) as proto:
        proto.register_cap("foo")
        proto.register_cap("bar")
        proto.register("001", _on_001)
        await proto.connect()
        await fut
        proto.quit()
        await proto.quit_future

    assert server.lines == [
        (
            "in",
            "CAP LS 302",
        ),
        (
            "out",
            ":irc.example.com CAP * LS :foo sasl=EXTERNAL bar",
        ),
        (
            "in",
            "NICK nick",
        ),
        (
            "in",
            "USER nick 0 * :nick",
        ),
        (
            "in",
            "CAP REQ :foo",
        ),
        (
            "out",
            ":irc.example.com CAP * ACK :foo",
        ),
        (
            "in",
            "CAP REQ :sasl",
        ),
        (
            "out",
            ":irc.example.com CAP * ACK :sasl",
        ),
        (
            "in",
            "CAP REQ :bar",
        ),
        (
            "out",
            ":irc.example.com CAP * ACK :bar",
        ),
        (
            "in",
            "CAP END",
        ),
        (
            "out",
            ":irc.example.com PING foobar",
        ),
        ("in", "PONG foobar"),
        (
            "out",
            ":irc.example.com 001",
        ),
        ("in", "PRIVMSG #foo :bar"),
        (
            "in",
            "QUIT",
        ),
    ]


async def test_connect_ssl() -> None:
    """Test sasl flow."""
    fut = asyncio.Future[None]()

    async def _on_001(_conn: IrcProtocol, _msg: Message) -> None:
        _conn.send_command(Message.parse("PRIVMSG #foo :bar"))
        fut.set_result(None)

    server = MockServer(is_ssl=True)

    logging.getLogger("asyncio").setLevel(0)

    with IrcProtocol(
        [server],
        "nick",
        sasl_auth=("foo", "bar"),
        sasl_mech=SASLMechanism.PLAIN,
        logger=logging.getLogger("asyncirc"),
    ) as proto:
        proto.register_cap("foo")
        proto.register_cap("bar")
        proto.register("001", _on_001)
        await proto.connect()
        await fut
        proto.quit()
        await proto.quit_future

    assert server.lines == [
        (
            "in",
            "CAP LS 302",
        ),
        (
            "out",
            ":irc.example.com CAP * LS :foo sasl bar",
        ),
        (
            "in",
            "NICK nick",
        ),
        (
            "in",
            "USER nick 0 * :nick",
        ),
        (
            "in",
            "CAP REQ :foo",
        ),
        (
            "out",
            ":irc.example.com CAP * ACK :foo",
        ),
        (
            "in",
            "CAP REQ :sasl",
        ),
        (
            "out",
            ":irc.example.com CAP * ACK :sasl",
        ),
        (
            "in",
            "CAP REQ :bar",
        ),
        (
            "out",
            ":irc.example.com CAP * ACK :bar",
        ),
        (
            "in",
            "AUTHENTICATE PLAIN",
        ),
        (
            "out",
            ":irc.example.com AUTHENTICATE +",
        ),
        (
            "in",
            "AUTHENTICATE Zm9vAGZvbwBiYXI=",
        ),
        (
            "out",
            ":irc.example.com 903",
        ),
        (
            "in",
            "CAP END",
        ),
        (
            "out",
            ":irc.example.com PING foobar",
        ),
        ("in", "PONG foobar"),
        (
            "out",
            ":irc.example.com 001",
        ),
        ("in", "PRIVMSG #foo :bar"),
        (
            "in",
            "QUIT",
        ),
    ]
