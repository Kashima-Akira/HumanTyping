# Local timing fixes

The Playwright sync and async adapters now accept
`HumanTyper(wpm=70, key_hold_ms=50)`. This sets the time between keydown and
keyup, including Backspace. The default is a fixed 50 ms for reproducible
testing; it is not a measured human typing model or an anti-detection guarantee.
Use `key_hold_ms=0` for the original no-explicit-hold behavior.

The adapter subtracts the previous configured hold from the next modeled
interval so it does not add that hold twice. Browser/driver overhead still adds
time, and intervals shorter than the hold are limited by that hold. Overlapping
keys are not modeled. Selenium and Appium retain their existing hold behavior.

Swap errors now produce two timestamped history entries with the intermediate
text, preserving the model's first and second intervals. The first is labeled
`TYPED_SWAP`, the second `TYPED_SWAP_CONTINUED`. `step()` still returns the final
entry for a swap; `run()` returns the full history with both entries. The demo
counts the two entries as one swap error. All adapters consume the split history.

## Run

From this folder, using the installed local virtual environment:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python examples/timing_check.py --keep-open
```

The browser demo uses a local, in-memory page. It first forces a swap with
120/180 ms model intervals and corrects the result, then runs a normal text
simulation. It checks the final text, actual key hold times and swap interval.
Results and a screenshot are saved under `test-results/`.
Close the test browser window to exit. Use `--headless` for a nonvisual run.

The normal demo now targets 22.5 WPM. Its `PeriodicPauseElement` adapter waits
for a uniformly random 1–10 seconds after each approximately ten seconds of
typing, checking between complete key presses. Pause time is excluded from the
next ten-second window. The page shows each pause, and the report records its
requested and actual duration. The short controlled swap probe stays unchanged.

These checks do not access Ed, submit course work, or test any site's detection.
