from __future__ import annotations

import time
import asyncio
import math
from collections.abc import Iterable
from typing import Any

from .typer import MarkovTyper


def _extract_char(action: str) -> str:
    """Extract the typed character(s) from an action string like TYPED 'x' or TYPED_SWAP 'ht'."""
    first_quote = action.index("'")
    last_quote = action.rindex("'")
    return action[first_quote + 1:last_quote]


def _typing_history(text: str, wpm: float, layout: str) -> Iterable[tuple[float, str, Any]]:
    if not isinstance(text, str) or len(text) == 0:
        raise ValueError("text must be a non-empty string")

    typer = MarkovTyper(text, target_wpm=wpm, layout=layout)
    _, history = typer.run()
    return history


class HumanTyper:
    """
    A helper class to integrate realistic typing into automation frameworks
    like Playwright, Selenium, or Appium.
    """

    def __init__(self, wpm: float = 60.0, layout: str = "qwerty", *, key_hold_ms: float = 50.0) -> None:
        if not isinstance(wpm, (int, float)) or wpm <= 0:
            raise ValueError("wpm must be a positive number")
        self.wpm = wpm
        self.layout = layout
        if not isinstance(key_hold_ms, (int, float)) or not math.isfinite(key_hold_ms) or key_hold_ms < 0:
            raise ValueError("key_hold_ms must be a finite non-negative number")
        # Playwright only: an explicit, configurable dwell time, not a detector bypass.
        self.key_hold_ms = key_hold_ms

    def _playwright_events(self, text: str):
        last_time = 0.0
        previous_hold = 0.0
        for t, action, _ in _typing_history(text, self.wpm, self.layout):
            if "BACKSPACE" in action:
                keys = ["Backspace"]
            elif "TYPED" in action:
                keys = list(_extract_char(action))
            else:
                continue
            # New histories have one character per event. Split legacy grouped
            # events evenly, since their individual timestamps are unavailable.
            interval = (t - last_time) / len(keys)
            for key in keys:
                yield max(0.0, interval - previous_hold), key
                previous_hold = self.key_hold_ms / 1000.0
            last_time = t

    async def type(self, page_element: Any, text: str) -> None:
        """
        Types text into a Playwright element with realistic human behavior.

        This is the main method for Playwright integration. It simulates:
        - Variable typing speed based on word complexity
        - Realistic errors (neighbor keys, swaps)
        - Natural corrections with backspace
        - Fatigue over longer texts

        Args:
            page_element: The Playwright Locator or ElementHandle to type into.
            text: The text to type with human-like behavior.

        Example:
            typer = HumanTyper(wpm=70)
            input_box = page.locator("input[name='search']")
            await input_box.click()
            await typer.type(input_box, "Hello world!")
        """
        for delay, key in self._playwright_events(text):
            if delay > 0:
                await asyncio.sleep(delay)
            await page_element.press(key, delay=self.key_hold_ms)

    def type_appium(self, driver: Any, text: str) -> None:
        """
        Types text into the focused mobile element using W3C Actions.
        This operates at the driver level and requires the element to be focused.

        Args:
            driver: The Appium WebDriver.
            text: The text to type.

        Example:
            typer = HumanTyper(wpm=45)
            search_box = driver.find_element(...)
            search_box.click()  # Ensure focus
            typer.type_appium(driver, "Hello Appium")
        """
        history = _typing_history(text, self.wpm, self.layout)
        last_time = 0.0

        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.common.keys import Keys

        for t, action, _ in history:
            delay = t - last_time
            if delay > 0:
                time.sleep(delay)
            last_time = t

            actions = ActionChains(driver)
            if "BACKSPACE" in action:
                actions.send_keys(Keys.BACK_SPACE).perform()
            elif "TYPED_SWAP" in action:
                for char in _extract_char(action):
                    actions.send_keys(char)
                actions.perform()
            elif "TYPED" in action:  # Handles TYPED, TYPED_ERROR
                char = _extract_char(action)
                actions.send_keys(char).perform()

    def type_sync(self, element: Any, text: str) -> None:
        """
        Types text into a Playwright sync element or Selenium WebElement with
        realistic human behavior.

        Args:
            element: The Playwright sync Locator/ElementHandle or Selenium
                WebElement to type into.
            text: The text to type with human-like behavior.

        Example:
            typer = HumanTyper(wpm=65)
            input_box = page.locator("input[name='search']")
            input_box.click()
            typer.type_sync(input_box, "Hello Playwright sync!")
        """
        if hasattr(element, "press"):
            self._type_playwright_sync(element, text)
            return

        self._type_selenium_sync(element, text)

    def _type_playwright_sync(self, page_element: Any, text: str) -> None:
        for delay, key in self._playwright_events(text):
            if delay > 0:
                time.sleep(delay)
            page_element.press(key, delay=self.key_hold_ms)

    def _type_selenium_sync(self, selenium_element: Any, text: str) -> None:
        history = _typing_history(text, self.wpm, self.layout)
        last_time = 0.0

        from selenium.webdriver.common.keys import Keys

        for t, action, _ in history:
            delay = t - last_time
            if delay > 0:
                time.sleep(delay)
            last_time = t

            if "BACKSPACE" in action:
                selenium_element.send_keys(Keys.BACK_SPACE)
            elif "TYPED_SWAP" in action:
                for char in _extract_char(action):
                    selenium_element.send_keys(char)
            elif "TYPED" in action:  # Handles TYPED, TYPED_ERROR
                char = _extract_char(action)
                selenium_element.send_keys(char)
