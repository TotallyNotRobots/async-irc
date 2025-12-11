# SPDX-FileCopyrightText: 2017-2020 Snoonet
# SPDX-FileCopyrightText: 2020-present linuxdaemon <linuxdaemon.irc@gmail.com>
#
# SPDX-License-Identifier: MIT

"""Import tests."""


async def test_imports() -> None:
    """Test basic init of IrcProtocol."""
    from asyncirc.protocol import IrcProtocol

    with IrcProtocol([], "") as proto:
        assert not proto.connected
