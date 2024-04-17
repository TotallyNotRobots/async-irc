"""Import tests."""


async def test_imports() -> None:
    """Test basic init of IrcProtocol."""
    from asyncirc.protocol import IrcProtocol

    with IrcProtocol([], "") as proto:
        assert not proto.connected
