"""
Skipped checks must never cost a candidate points.

The SELinux (and network-role, and spare-disk) tasks can't be observed in
every lab, so they record those checks as skipped. That is only safe if
skipped checks are excluded from BOTH the pass decision and the score
denominator — otherwise a correct answer silently scores lower on a lab
that simply couldn't look.
"""

from core.validator import ValidationResult
from tasks.selinux import SeBooleanTask


def test_skipped_checks_are_excluded_from_scoring():
    res = ValidationResult(task_id="t", max_score=20)
    res.add("a", True).add("b", True)
    res.add_skip("needs a real VM", "no selinuxfs here")
    # 2/2 gradeable, not 2/3 — the skip must not dilute the score.
    assert res.score == 20
    assert res.passed
    assert len(res.gradeable) == 2
    assert len(res.skipped) == 1


def test_skipped_check_does_not_mask_a_real_failure():
    res = ValidationResult(task_id="t", max_score=20)
    res.add("a", True).add("b", False)
    res.add_skip("unobservable", "reason")
    assert not res.passed
    assert res.score == 10          # 1 of 2 gradeable


def test_all_skipped_is_not_a_free_pass():
    """Nothing was proven, so nothing is awarded."""
    res = ValidationResult(task_id="t", max_score=20)
    res.add_skip("x", "reason").add_skip("y", "reason")
    assert not res.passed
    assert res.score == 0


def test_selinux_task_skips_instead_of_failing_when_unavailable(workdir, monkeypatch):
    """A CORRECT playbook on a lab with no SELinux must score full marks on
    what can be graded, and record the rest as skipped rather than failed."""
    task = SeBooleanTask().generate()
    boolean = task.params["boolean"]
    (workdir / "seboolean.yml").write_text(
        "---\n"
        "- hosts: all\n"
        "  become: true\n"
        "  tasks:\n"
        "    - ansible.posix.seboolean:\n"
        f"        name: {boolean}\n"
        "        state: true\n"
        "        persistent: true\n"
    )
    # Simulate a lab whose nodes have no live SELinux subsystem.
    monkeypatch.setattr(type(task), "selinux_available", lambda self: False)

    res = task.validate()
    assert res.skipped, "should have recorded a skipped check"
    assert res.passed, [c.name for c in res.gradeable if not c.passed]
    assert res.score == task.points
    reason = res.skipped[0].detail
    assert "selinux" in reason.lower() and "VM" in reason


def test_selinux_task_still_fails_a_wrong_playbook_when_unavailable(workdir, monkeypatch):
    """Skipping execution must not turn into skipping grading — a playbook
    missing persistent: true is still wrong on any lab."""
    task = SeBooleanTask().generate()
    (workdir / "seboolean.yml").write_text(
        "---\n"
        "- hosts: all\n"
        "  tasks:\n"
        "    - ansible.posix.seboolean:\n"
        f"        name: {task.params['boolean']}\n"
        "        state: true\n"
    )
    monkeypatch.setattr(type(task), "selinux_available", lambda self: False)

    res = task.validate()
    assert not res.passed
    failed = [c.name for c in res.gradeable if not c.passed]
    assert any("persistent" in name for name in failed), failed
