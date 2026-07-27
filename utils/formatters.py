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


def skip(text: str) -> str:
    return f"{C.YELLOW}⊘ {text}{C.RESET}"


def dim(text: str) -> str:
    return f"{C.DIM}{text}{C.RESET}"


def score_line(score: int, max_score: int, pass_percent: int) -> str:
    """Render the result, and also express it the way Red Hat does.

    Red Hat reports performance exams as a total on a 0-300 scale with 210
    to pass; showing that alongside the raw points makes the number look
    like the one Certification Central gives you. See
    settings.RH_SCORE_SCALE for why that figure is community-attested
    rather than published by Red Hat.
    """
    from config.settings import RH_PASS_SCORE, RH_SCORE_SCALE

    pct = round(100 * score / max_score) if max_score else 0
    verdict = (f"{C.GREEN}PASS{C.RESET}" if pct >= pass_percent
               else f"{C.RED}FAIL{C.RESET}")
    rh = round(RH_SCORE_SCALE * score / max_score) if max_score else 0
    return (f"{C.BOLD}Score: {score}/{max_score} ({pct}%) — {verdict}"
            f"{C.DIM}  (pass mark {pass_percent}%)\n"
            f"Red Hat-style total: {rh}/{RH_SCORE_SCALE} "
            f"(pass {RH_PASS_SCORE}/{RH_SCORE_SCALE}){C.RESET}")
