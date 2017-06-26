# coding=utf-8
from pytest import raises

from asyncirc.irc import MessageTag, Cap, CapList


class TestCaps:
    def test_cap_list(self):
        cases = (
            (
                "blah blah-blah cap-1 test-cap=value-data",
                (("blah", None), ("blah-blah", None), ("cap-1", None), ("test-cap", "value-data"))
            ),
        )

        for text, expected in cases:
            parsed = CapList.parse(text)
            assert len(parsed) == len(expected)
            for (name, value), actual in zip(expected, parsed):
                assert actual.name == name
                assert actual.value == value

    def test_caps(self):
        cases = (
            ("vendor.example.org/cap-name", "vendor.example.org/cap-name", None),
        )

        for text, name, value in cases:
            cap = Cap.parse(text)
            assert cap.name == name
            assert cap.value == value


def test_message_tags():
    cases = (
        ("a=b", "a", "b"),
        ("test/blah=", "test/blah", None),
        ("blah=aa\\r\\n\\:\\\\", "blah", "aa\r\n;\\"),
    )
    for text, name, value in cases:
        tag = MessageTag.parse(text)
        assert tag.name == name
        assert tag.value == value

    with raises(ValueError):
        MessageTag.parse("key=value\\")
