"""
Exam clock.

The real EX294 is a fixed-length practical, and running out of time is a
normal way to fail it. A session that lets you think for as long as you
like trains the wrong instinct, so `--exam` runs against a clock.

Deliberately advisory rather than enforced: it warns, and it reports how
long you took, but it does not rip the session away mid-task. Being cut off
at a hard boundary teaches nothing you can act on, while "you were 40
minutes over" tells you exactly what to fix. The remaining time is shown in
the prompt so it's impossible to lose track of.

Red Hat does not publish EX294's duration; the 4-hour figure is
long-standing community consensus. See exam_objectives.UNPUBLISHED_NUMBERS_NOTE
— it is a realistic default, not an official one.
"""

import time

from config.settings import C


class ExamClock:
    """Counts down from a fixed budget. Never blocks, never interrupts."""

    # Fractions of the budget remaining at which to warn, high to low.
    WARN_AT = (0.5, 0.25, 0.1)

    def __init__(self, minutes: int):
        self.budget = max(0, int(minutes)) * 60
        self.started = time.monotonic()
        self._warned = set()

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started

    @property
    def remaining(self) -> float:
        """Seconds left; negative once over budget."""
        return self.budget - self.elapsed

    @property
    def expired(self) -> bool:
        return self.remaining <= 0

    @staticmethod
    def _hms(seconds: float) -> str:
        seconds = int(abs(seconds))
        return f"{seconds // 3600}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"

    def label(self) -> str:
        """Short clock for the prompt, coloured by urgency."""
        if self.expired:
            return f"{C.RED}-{self._hms(self.remaining)}{C.RESET}"
        fraction = self.remaining / self.budget if self.budget else 1
        colour = C.GREEN if fraction > 0.25 else C.YELLOW
        return f"{colour}{self._hms(self.remaining)}{C.RESET}"

    def due_warning(self):
        """Warning string to print once per threshold crossed, else None.

        Called from the session loop between commands, so a candidate deep
        in one task only sees it when they next surface — which is the
        point at which they can actually change what they're doing.
        """
        if not self.budget:
            return None
        if self.expired:
            if "over" not in self._warned:
                self._warned.add("over")
                return (f"Time is up ({self._hms(self.budget)} used). The "
                        f"session keeps going and still grades — note how "
                        f"far over you run, that's the useful part.")
            return None
        fraction = self.remaining / self.budget
        for threshold in self.WARN_AT:
            if fraction <= threshold and threshold not in self._warned:
                self._warned.add(threshold)
                return f"{self._hms(self.remaining)} remaining."
        return None

    def summary(self) -> str:
        used = self._hms(self.elapsed)
        if not self.budget:
            return f"Time taken: {used}"
        if self.expired:
            return (f"Time taken: {used} of {self._hms(self.budget)} — "
                    f"{self._hms(self.remaining)} OVER.")
        return (f"Time taken: {used} of {self._hms(self.budget)} — "
                f"{self._hms(self.remaining)} to spare.")
