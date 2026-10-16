"""Local browser timing check. No external site or account is accessed."""
import argparse
import json
import random
import time
from pathlib import Path
from unittest.mock import patch

from playwright.sync_api import sync_playwright

from humantyping import HumanTyper, MarkovTyper


PAGE = """<!doctype html><html lang="en"><meta charset="utf-8">
<title>HumanTyping — local timing check</title>
<style>
body{font:16px system-ui;background:#f4f6fa;color:#192434;max-width:1000px;margin:36px auto;padding:0 24px}
h1{font-size:28px}textarea{display:block;width:95%;padding:14px;font:19px monospace;margin:12px 0 24px}
section{background:white;padding:24px;border-radius:16px;margin:20px 0}
pre{white-space:pre-wrap;line-height:1.7}table{width:100%;border-collapse:collapse}
td,th{text-align:left;padding:8px;border-bottom:1px solid #ddd}
</style>
<h1>HumanTyping · Local timing check</h1>
<p>This page measures keyboard events locally. It does not test Ed detection.</p>
<section><label for="probe">Controlled swap: type “ba”, correct to “ab”</label>
<textarea id="probe" rows="1"></textarea>
<label for="sample">Normal simulation</label><textarea id="sample" rows="2"></textarea></section>
<section><h2>Measured results</h2><pre id="summary">Running…</pre></section>
<section><h2>Controlled swap events</h2><table><thead><tr><th>Event</th><th>Key</th><th>Time (ms)</th></tr></thead>
<tbody id="events"></tbody></table></section>
<script>
window.recorded = [];
for (const id of ['probe', 'sample']) {
  const el = document.getElementById(id);
  for (const type of ['keydown', 'keyup']) el.addEventListener(type, e => {
    const item = {field:id, type, key:e.key, time:performance.now()};
    window.recorded.push(item);
    if (id === 'probe') {
      const row = document.getElementById('events').insertRow();
      for (const v of [type, e.key, item.time.toFixed(1)]) row.insertCell().textContent = v;
    }
  });
}
</script></html>"""


def probe_history():
    model = MarkovTyper("ab")
    with patch("humantyping.typer.PROB_SWAP_ERROR", 1), patch.object(
        model, "_calculate_keystroke_time", side_effect=[0.12, 0.18]
    ):
        model.step()
    with patch("humantyping.typer.PROB_SWAP_ERROR", 0), patch("humantyping.typer.PROB_ERROR", 0):
        _, history = model.run()
    assert model.state.current_text == "ab"
    return history


class PeriodicPauseElement:
    """Pause between complete keystrokes after each ten seconds of typing.

    The pause itself is excluded from the next ten-second window.
    This adapter is used only by the demo's normal simulation.
    """

    def __init__(self, element, page):
        self.element = element
        self.page = page
        self.next_pause = time.monotonic() + 10
        self.pauses = []

    def press(self, key, *, delay):
        if time.monotonic() >= self.next_pause:
            seconds = random.uniform(1, 10)
            message = f"Paused for {seconds:.1f} seconds · target 22.5 WPM"
            self.page.locator("#summary").evaluate("(el, value) => el.textContent = value", message)
            print(message, flush=True)
            started = time.monotonic()
            self.page.wait_for_timeout(seconds * 1000)
            self.pauses.append({"requested_seconds": seconds, "actual_seconds": time.monotonic() - started})
            self.page.locator("#summary").evaluate(
                "(el) => el.textContent = 'Typing at target 22.5 WPM · next pause in about 10 seconds'"
            )
            self.next_pause = time.monotonic() + 10
        self.element.press(key, delay=delay)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--keep-open", action="store_true")
    args = parser.parse_args()
    output = Path(__file__).resolve().parents[1] / "test-results"
    output.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        page = browser.new_page(viewport={"width": 1100, "height": 1000})
        page.set_content(PAGE)
        typer = HumanTyper(wpm=22.5, key_hold_ms=50)
        with patch("humantyping.integration._typing_history", return_value=probe_history()):
            typer.type_sync(page.locator("#probe"), "ab")
        sample = "Hello, HumanTyping! Timing test. Watch the pauses between typing."
        page.locator("#summary").evaluate(
            "(el) => el.textContent = 'Typing at target 22.5 WPM · random 1–10 second pause every 10 seconds'"
        )
        paused_element = PeriodicPauseElement(page.locator("#sample"), page)
        typer.type_sync(paused_element, sample)
        events = page.evaluate("window.recorded")
        probe = [event for event in events if event["field"] == "probe"]
        downs = [event for event in probe if event["type"] == "keydown"]
        holds = []
        for down, up in zip(probe[::2], probe[1::2]):
            assert down["type"] == "keydown" and up["type"] == "keyup"
            assert down["key"] == up["key"]
            holds.append(up["time"] - down["time"])
        gap = downs[1]["time"] - downs[0]["time"]
        assert [e["key"] for e in downs[:2]] == ["b", "a"]
        assert min(holds) >= 40, holds
        assert gap >= 144, gap  # 80% of the planned 180 ms, tolerant of timers.
        assert page.locator("#probe").input_value() == "ab"
        assert page.locator("#sample").input_value() == sample
        pause_summary = ", ".join(f"{item['actual_seconds']:.1f}s" for item in paused_element.pauses)
        summary = (
            "PASS — both final texts match.\n"
            "Target speed: 22.5 WPM; random pause after every ~10 seconds of typing.\n"
            f"Pauses: {pause_summary or 'none'}\n"
            f"Configured key hold: 50 ms; measured: {min(holds):.1f}–{max(holds):.1f} ms\n"
            f"Swap keydown interval: planned 180 ms; measured {gap:.1f} ms\n"
            "Browser/driver overhead can add time. These are timing checks, not detection tests."
        )
        page.locator("#summary").evaluate("(el, value) => el.textContent = value", summary)
        (output / "timing-report.json").write_text(json.dumps({
            "summary": summary, "events": events,
            "hold_ms": holds, "swap_gap_ms": gap,
            "target_wpm": 22.5, "pauses": paused_element.pauses,
        }, indent=2), encoding="utf-8")
        page.screenshot(path=str(output / "timing-check.png"), full_page=True)
        print(summary, flush=True)
        print(f"Results: {output}", flush=True)
        if args.keep_open:
            print("Close the test browser window when finished.", flush=True)
            try:
                page.wait_for_event("close", timeout=0)
            except KeyboardInterrupt:
                pass
        browser.close()


if __name__ == "__main__":
    main()
