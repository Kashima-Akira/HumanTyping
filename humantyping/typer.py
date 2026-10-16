from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field

from .config import (
    DEFAULT_WPM, WPM_STD, AVG_WORD_LENGTH,
    PROB_ERROR, PROB_SWAP_ERROR, PROB_NOTICE_ERROR,
    SPEED_BOOST_COMMON_WORD, SPEED_PENALTY_COMPLEX_WORD,
    SPEED_BOOST_CLOSE_KEYS, SPEED_BOOST_BIGRAM,
    TIME_KEYSTROKE_STD, TIME_BACKSPACE_MEAN, TIME_BACKSPACE_STD,
    TIME_REACTION_MEAN, TIME_REACTION_STD,
    TIME_DIRECT_ACCENT_PENALTY, TIME_COMPOSED_ACCENT_PENALTY,
    TIME_UPPERCASE_PENALTY, TIME_SPACE_PAUSE_MEAN, TIME_SPACE_PAUSE_STD,
    FATIGUE_FACTOR, FATIGUE_CAP,
    DRIFT_CORRECTION_PROB, COMPLEX_WORD_ERROR_MULT,
    COMMON_WORD_ERROR_MULT, COMPOSED_ACCENT_ERROR_MULT,
    FAR_KEY_PENALTY, FAR_KEY_THRESHOLD, CLOSE_KEY_THRESHOLD,
    MIN_KEYSTROKE_TIME, MIN_REACTION_TIME, MIN_BACKSPACE_TIME,
    MIN_SPEED_MULTIPLIER,
)
from .keyboard import KeyboardLayout
from .language import get_word_difficulty, is_common_bigram


@dataclass
class TypingState:
    current_text: str = ""
    target_text: str = ""
    total_time: float = 0.0
    history: list[tuple[float, str, str]] = field(default_factory=list)
    last_char_typed: str | None = None
    fatigue_multiplier: float = 1.0
    mental_cursor_pos: int = 0


class MarkovTyper:
    def __init__(self, target_text: str, target_wpm: float = DEFAULT_WPM, layout: str = "qwerty"):
        if not isinstance(target_text, str) or len(target_text) == 0:
            raise ValueError("target_text must be a non-empty string")
        if not isinstance(target_wpm, (int, float)) or target_wpm <= 0:
            raise ValueError("target_wpm must be a positive number")

        self.target_text = target_text
        self.keyboard = KeyboardLayout(layout)
        self.state = TypingState(target_text=target_text)

        self.session_wpm = np.random.normal(target_wpm, WPM_STD)
        self.session_wpm = max(10, self.session_wpm)
        self.base_keystroke_time = 60 / (self.session_wpm * AVG_WORD_LENGTH)

        self.state.history.append((0.0, f"INIT (WPM: {self.session_wpm:.1f})", ""))

    def _get_current_word_context(self) -> str | None:
        idx = self.state.mental_cursor_pos
        if idx >= len(self.target_text):
            return None
        start = idx
        while start > 0 and self.target_text[start - 1] != ' ':
            start -= 1
        end = idx
        while end < len(self.target_text) and self.target_text[end] != ' ':
            end += 1
        return self.target_text[start:end]

    def _calculate_keystroke_time(self, char_to_type: str) -> float:
        keystroke_time = self.base_keystroke_time * self.state.fatigue_multiplier

        current_word = self._get_current_word_context()
        if current_word:
            difficulty = get_word_difficulty(current_word)
            if difficulty == "common":
                keystroke_time *= SPEED_BOOST_COMMON_WORD
            elif difficulty == "complex":
                keystroke_time *= SPEED_PENALTY_COMPLEX_WORD

        if self.state.last_char_typed:
            if is_common_bigram(self.state.last_char_typed, char_to_type):
                keystroke_time *= SPEED_BOOST_BIGRAM
            else:
                dist = self.keyboard.get_distance(self.state.last_char_typed, char_to_type)
                if 0 < dist < CLOSE_KEY_THRESHOLD:
                    keystroke_time *= SPEED_BOOST_CLOSE_KEYS
                elif dist > FAR_KEY_THRESHOLD:
                    keystroke_time *= FAR_KEY_PENALTY

        if char_to_type == ' ':
            keystroke_time += np.random.normal(TIME_SPACE_PAUSE_MEAN, TIME_SPACE_PAUSE_STD)
        elif self.keyboard.is_composed_accent(char_to_type):
            keystroke_time += TIME_COMPOSED_ACCENT_PENALTY
        elif self.keyboard.is_direct_accent(char_to_type):
            keystroke_time += TIME_DIRECT_ACCENT_PENALTY
        elif char_to_type.isupper():
            keystroke_time += TIME_UPPERCASE_PENALTY

        # Apply floor to prevent unrealistic stacking of boosts
        keystroke_time = max(MIN_SPEED_MULTIPLIER * self.base_keystroke_time, keystroke_time)

        dt = np.random.normal(keystroke_time, TIME_KEYSTROKE_STD)
        return max(MIN_KEYSTROKE_TIME, dt)

    def step(self) -> tuple[float, str, str] | None:
        # 1. Check for completion
        if self.state.current_text == self.target_text:
            return None

        # --- MONITORING & CORRECTION PHASE ---

        # Calculate divergence point
        first_error_pos = len(self.target_text)
        min_len = min(len(self.state.current_text), len(self.target_text))
        for i in range(min_len):
            if self.state.current_text[i] != self.target_text[i]:
                first_error_pos = i
                break

        # Also consider over-typing as an error
        if len(self.state.current_text) > len(self.target_text) and first_error_pos == len(self.target_text):
            first_error_pos = len(self.target_text)

        # Do we have an error?
        if first_error_pos < len(self.state.current_text):
            should_correct = False

            last_action = self.state.history[-1][1] if self.state.history else ""

            # Case 0: CONTINUED BACKSPACING (Critical)
            if "BACKSPACE" in last_action:
                should_correct = True

            # Case A: End of text (Always correct)
            elif self.state.mental_cursor_pos >= len(self.target_text):
                should_correct = True

            # Case B: End of Word / Context Check
            elif len(self.state.current_text) > 0:
                last_char = self.state.current_text[-1]
                distance = len(self.state.current_text) - first_error_pos

                # Check at word boundaries (Strict)
                if last_char in ' \n\t.,;!?:()[]{}<>"\'':
                    should_correct = True

                # Drift Check (Don't let errors linger)
                elif distance >= 2:
                    if np.random.random() < DRIFT_CORRECTION_PROB:
                        should_correct = True

                # Immediate reaction (1 char past error)
                elif distance == 1:
                    if np.random.random() < PROB_NOTICE_ERROR:
                        should_correct = True

            if should_correct:
                # Reaction time (only if we weren't already backspacing)
                if "BACKSPACE" not in last_action:
                    dt = np.random.normal(TIME_REACTION_MEAN, TIME_REACTION_STD)
                    self.state.total_time += max(MIN_REACTION_TIME, dt)

                # Perform Backspace
                dt = max(MIN_BACKSPACE_TIME, np.random.normal(TIME_BACKSPACE_MEAN, TIME_BACKSPACE_STD))
                self.state.total_time += dt
                self.state.current_text = self.state.current_text[:-1]

                event = (self.state.total_time, "BACKSPACE", self.state.current_text)
                self.state.history.append(event)

                # Sync mental cursor immediately
                self.state.mental_cursor_pos = len(self.state.current_text)
                return event

        # --- TYPING PHASE ---

        # Sync mental cursor if we backspaced (redundant safety)
        if self.state.mental_cursor_pos > len(self.state.current_text):
            self.state.mental_cursor_pos = len(self.state.current_text)

        if self.state.mental_cursor_pos >= len(self.target_text):
            return None

        char_intended = self.target_text[self.state.mental_cursor_pos]

        # If the character is not on our keyboard, type it literally (no error modeling)
        if not self.keyboard.has_key(char_intended) and char_intended != ' ':
            self.state.fatigue_multiplier = min(FATIGUE_CAP, self.state.fatigue_multiplier * FATIGUE_FACTOR)
            dt = self.base_keystroke_time * self.state.fatigue_multiplier
            dt = max(MIN_KEYSTROKE_TIME, np.random.normal(dt, TIME_KEYSTROKE_STD))
            self.state.total_time += dt
            self.state.current_text += char_intended
            self.state.last_char_typed = char_intended
            event = (self.state.total_time, f"TYPED '{char_intended}'", self.state.current_text)
            self.state.history.append(event)
            self.state.mental_cursor_pos += 1
            return event

        self.state.fatigue_multiplier = min(FATIGUE_CAP, self.state.fatigue_multiplier * FATIGUE_FACTOR)

        # Swap Error (Anticipation)
        # Example: "the" -> "hte". We type char_after first, then char_intended.
        if len(self.target_text) > self.state.mental_cursor_pos + 1:
            char_after = self.target_text[self.state.mental_cursor_pos + 1]
            if char_after != ' ' and char_after != char_intended:
                if np.random.random() < PROB_SWAP_ERROR:
                    # Type the anticipated character first
                    dt1 = self._calculate_keystroke_time(char_after)
                    self.state.total_time += dt1
                    self.state.current_text += char_after
                    self.state.last_char_typed = char_after
                    self.state.history.append((
                        self.state.total_time, f"TYPED_SWAP '{char_after}'", self.state.current_text
                    ))

                    # Then type the intended character (producing a real swap)
                    dt2 = self._calculate_keystroke_time(char_intended)
                    self.state.total_time += dt2
                    self.state.current_text += char_intended

                    self.state.last_char_typed = char_intended
                    event = (self.state.total_time, f"TYPED_SWAP_CONTINUED '{char_intended}'", self.state.current_text)
                    self.state.history.append(event)
                    self.state.mental_cursor_pos += 2
                    return event

        # Normal Typing (Success or Error)
        current_prob_error = PROB_ERROR
        word_diff = get_word_difficulty(self._get_current_word_context() or "")
        if word_diff == "complex":
            current_prob_error *= COMPLEX_WORD_ERROR_MULT
        elif word_diff == "common":
            current_prob_error *= COMMON_WORD_ERROR_MULT
        if self.keyboard.is_composed_accent(char_intended):
            current_prob_error *= COMPOSED_ACCENT_ERROR_MULT

        if np.random.random() < current_prob_error:
            # Generate Error
            wrong_char = self.keyboard.get_random_neighbor(char_intended)
            dt = self._calculate_keystroke_time(wrong_char)
            self.state.total_time += dt
            self.state.current_text += wrong_char
            self.state.last_char_typed = wrong_char
            event = (self.state.total_time, f"TYPED_ERROR '{wrong_char}'", self.state.current_text)
            self.state.history.append(event)
            self.state.mental_cursor_pos += 1
        else:
            # Success
            dt = self._calculate_keystroke_time(char_intended)
            self.state.total_time += dt
            self.state.current_text += char_intended
            self.state.last_char_typed = char_intended
            event = (self.state.total_time, f"TYPED '{char_intended}'", self.state.current_text)
            self.state.history.append(event)
            self.state.mental_cursor_pos += 1

        return event

    def run(self) -> tuple[float, list[tuple[float, str, str]]]:
        steps = 0
        max_steps = len(self.target_text) * 10
        while self.step() is not None:
            steps += 1
            if steps > max_steps:
                break
        return self.state.total_time, self.state.history
