import asyncio
from unittest.mock import patch

import pytest

from humantyping import HumanTyper, MarkovTyper


def test_swap_preserves_each_timestamp_and_correction():
    typer = MarkovTyper("ab")
    with patch("humantyping.typer.PROB_SWAP_ERROR", 1), patch.object(
        typer, "_calculate_keystroke_time", side_effect=[0.1, 0.2]
    ):
        typer.step()
    first, second = typer.state.history[-2:]
    assert first[0] == pytest.approx(0.1)
    assert second[0] == pytest.approx(0.3)
    assert first[2] == "b"
    assert second[2] == "ba"
    assert typer.state.last_char_typed == "a"
    with patch("humantyping.typer.PROB_SWAP_ERROR", 0), patch("humantyping.typer.PROB_ERROR", 0):
        typer.run()
    assert typer.state.current_text == "ab"


@pytest.mark.parametrize("asynchronous", [False, True])
def test_playwright_holds_keys_without_double_counting_intervals(asynchronous):
    now = 0.0
    events = []

    def sleep(seconds):
        nonlocal now
        now += seconds

    async def async_sleep(seconds):
        sleep(seconds)

    def press(key, *, delay):
        events.append((key, "down", now))
        sleep(delay / 1000)
        events.append((key, "up", now))

    class SyncElement:
        def press(self, key, *, delay):
            press(key, delay=delay)

    class AsyncElement:
        async def press(self, key, *, delay):
            press(key, delay=delay)

    history = [(0, "INIT", ""), (0.1, "TYPED_SWAP 'b'", "b"),
               (0.3, "TYPED_SWAP_CONTINUED 'a'", "ba"),
               (0.5, "BACKSPACE", "b")]
    with patch("humantyping.integration._typing_history", return_value=history), \
         patch("humantyping.integration.time.sleep", sleep), \
         patch("humantyping.integration.asyncio.sleep", async_sleep):
        typer = HumanTyper(key_hold_ms=50)
        if asynchronous:
            asyncio.run(typer.type(AsyncElement(), "ab"))
        else:
            typer.type_sync(SyncElement(), "ab")
    assert [e[0] for e in events[::2]] == ["b", "a", "Backspace"]
    assert [e[2] for e in events[::2]] == pytest.approx([0.1, 0.3, 0.5])
    assert [up[2] - down[2] for down, up in zip(events[::2], events[1::2])] == pytest.approx([0.05] * 3)


@pytest.mark.parametrize("hold", [-1, float("nan"), float("inf"), "50"])
def test_invalid_hold_is_rejected(hold):
    with pytest.raises(ValueError, match="key_hold_ms"):
        HumanTyper(key_hold_ms=hold)
