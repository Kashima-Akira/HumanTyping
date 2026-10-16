from __future__ import annotations

from unittest.mock import patch

from humantyping.integration import HumanTyper


class FakeMarkovTyper:
    def __init__(self, text: str, target_wpm: float, layout: str) -> None:
        self.text = text
        self.target_wpm = target_wpm
        self.layout = layout

    def run(self):
        return self.text, [
            (0.0, "TYPED 'a'", None),
            (0.0, "TYPED_SWAP 'bc'", None),
            (0.0, "TYPED_ERROR 'x'", None),
            (0.0, "BACKSPACE", None),
        ]


class FakePlaywrightElement:
    def __init__(self) -> None:
        self.pressed: list[str] = []

    def press(self, key: str, *, delay: float = 0) -> None:
        self.pressed.append(key)


class FakeSeleniumElement:
    def __init__(self) -> None:
        self.sent_keys: list[str] = []

    def send_keys(self, key: str) -> None:
        self.sent_keys.append(key)


@patch("humantyping.integration.MarkovTyper", FakeMarkovTyper)
def test_type_sync_supports_playwright_sync_elements() -> None:
    element = FakePlaywrightElement()

    HumanTyper(wpm=70).type_sync(element, "abc")

    assert element.pressed == ["a", "b", "c", "x", "Backspace"]


@patch("humantyping.integration.MarkovTyper", FakeMarkovTyper)
def test_type_sync_keeps_selenium_fallback() -> None:
    element = FakeSeleniumElement()

    HumanTyper(wpm=70).type_sync(element, "abc")

    assert element.sent_keys[:4] == ["a", "b", "c", "x"]
    assert len(element.sent_keys) == 5


def test_type_sync_rejects_empty_text() -> None:
    element = FakePlaywrightElement()

    try:
        HumanTyper().type_sync(element, "")
    except ValueError as exc:
        assert str(exc) == "text must be a non-empty string"
    else:
        raise AssertionError("Expected ValueError")
