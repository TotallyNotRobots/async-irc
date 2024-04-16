async def test_imports() -> None:
    from asyncirc.protocol import IrcProtocol

    with IrcProtocol([], "") as proto:
        assert not proto.connected
