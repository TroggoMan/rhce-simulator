"""Terminal output helpers."""

from config.settings import C


def banner(text: str) -> str:
    bar = "=" * max(60, len(text) + 4)
    return f"{C.BOLD}{C.CYAN}{bar}\n  {text}\n{bar}{C.RESET}"


def ok(text: str) -> str:
    return f"{C.GREEN}✔ {text}{C.RESET}"


def fail(text: str) -> str:
    return f"{C.RED}✘ {text}{C.RESET}"


def warn(text: str) -> str:
    return f"{C.YELLOW}{text}{C.RESET}"


def dim(text: str) -> str:
    return f"{C.DIM}{text}{C.RESET}"


def score_line(score: int, max_score: int, pass_percent: int) -> str:
    pct = round(100 * score / max_score) if max_score else 0
    verdict = (f"{C.GREEN}PASS{C.RESET}" if pct >= pass_percent
               else f"{C.RED}FAIL{C.RESET}")
    return (f"{C.BOLD}Score: {score}/{max_score} ({pct}%) — {verdict}"
            f"{C.DIM}  (pass mark {pass_percent}%){C.RESET}")
