# coding=utf-8
"""
Server objects used for different stages in the connect process
to store contextual data
"""
from typing import Optional, Dict

from asyncirc.irc import Cap


class Server:
    """Represents a server to connect to"""

    def __init__(self, host: str, port: int, is_ssl: bool = False, password: str = None):
        self.host = host
        self.port = port
        self.password = password
        self.is_ssl = is_ssl

    def __str__(self) -> str:
        if self.is_ssl:
            return "{}:+{}".format(self.host, self.port)
        return "{}:{}".format(self.host, self.port)


class ConnectedServer(Server):
    """Represents a connected server

    Used to store session data like ISUPPORT tokens and enabled CAPs
    """

    def __init__(self, server):
        super().__init__(server.host, server.port, server.is_ssl, server.password)
        self.isupport_tokens: Dict[str, str] = {}
        self.caps: Dict[Cap, Optional[bool]] = {}
