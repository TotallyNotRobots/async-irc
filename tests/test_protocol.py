import asyncio
import logging
from ssl import SSLContext
from typing import Any, Callable, List, Mapping, Optional, Tuple, TypeVar

from irclib.parser import Message

from asyncirc.protocol import IrcProtocol, SASLMechanism
from asyncirc.server import BaseServer


class MockTransport(asyncio.Transport):
    def __init__(
        self,
        server: "MockServer",
        protocol: asyncio.BaseProtocol,
        extra: Optional[Mapping[str, Any]] = None,
    ) -> None:
        super().__init__(extra)
        self._server = server
        self._protocol = protocol
        self._write_buffer = b""

        self._received_user = False
        self._received_cap_ls = False
        self._received_nick = False
        self._received_cap_end = False
        self._registered = False

    def write(self, data: bytes) -> None:
        self._protocol.logger.info(data)
        self._write_buffer += data
        while b"\r\n" in self._write_buffer:
            part, self._write_buffer = self._write_buffer.split(b"\r\n", 1)
            msg = Message.parse(part)
            self._server.lines.append(("in", str(msg)))
            if msg.command == "CAP" and msg.parameters[0] == "LS":
                self._received_cap_ls = True
                self._server.send_line(
                    Message.parse(
                        ":irc.example.com CAP * LS :foo sasl=PLAIN bar"
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
            else:
                print(f"unhandled command: {msg}")

            if not self._registered:
                if (
                    self._received_nick
                    and self._received_user
                    and (not self._received_cap_ls or self._received_cap_end)
                ):
                    self._registered = True
                    self._server.send_line(
                        Message.parse(":irc.example.com 001")
                    )

    def set_protocol(self, protocol: asyncio.BaseProtocol) -> None:
        self._protocol = protocol

    def get_protocol(self) -> asyncio.BaseProtocol:
        return self._protocol


_ProtoT = TypeVar("_ProtoT", bound=asyncio.Protocol)


class MockServer(BaseServer):
    def __init__(
        self,
        *,
        password: Optional[str] = None,
        is_ssl: bool = False,
        ssl_ctx: Optional[SSLContext] = None,
        certpath: Optional[str] = None,
    ) -> None:
        super().__init__(
            password=password, is_ssl=is_ssl, ssl_ctx=ssl_ctx, certpath=certpath
        )
        self.lines: List[Tuple[str, str]] = []
        self.in_buffer = b""
        self.transport = None

    def send_line(self, msg: Message):
        self.transport.get_protocol().data_received(str(msg).encode() + b"\r\n")

    async def connect(
        self,
        protocol_factory: Callable[[], _ProtoT],
        *,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        **kwargs: Any,
    ) -> Tuple[asyncio.Transport, _ProtoT]:
        proto = protocol_factory()
        self.transport = MockTransport(self, proto)
        proto.connection_made(self.transport)
        return self.transport, proto


async def test_sasl() -> None:
    fut = asyncio.Future()

    async def _on_001(conn, msg):
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
            "in",
            "CAP REQ :sasl",
        ),
        (
            "in",
            "CAP REQ :bar",
        ),
        (
            "in",
            "AUTHENTICATE PLAIN",
        ),
        (
            "in",
            "AUTHENTICATE Zm9vAGZvbwBiYXI=",
        ),
        (
            "in",
            "CAP END",
        ),
        (
            "in",
            "QUIT",
        ),
    ]
