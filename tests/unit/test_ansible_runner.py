from pathlib import Path

from validators import ansible_runner as runner

RECAP = """
PLAY RECAP *********************************************************
node1  : ok=3 changed=1 unreachable=0 failed=0 skipped=0 rescued=0 ignored=0
node2  : ok=3 changed=0 unreachable=0 failed=1 skipped=0 rescued=0 ignored=0
"""


def test_parse_recap_extracts_all_hosts():
    recap = runner.parse_recap(RECAP)
    assert recap["node1"].changed == 1 and recap["node1"].failed == 0
    assert recap["node2"].failed == 1


def _fake_run_factory(outputs):
    """Return a run() stub that pops canned CmdResults per call."""
    calls = []

    def fake_run(cmd, cwd=None, timeout=None, env=None):
        calls.append(cmd)
        return outputs.pop(0)
    return fake_run, calls


def test_full_check_stops_on_syntax_error(monkeypatch):
    fake, calls = _fake_run_factory([runner.CmdResult(4, "", "syntax boom")])
    monkeypatch.setattr(runner, "run", fake)
    out = runner.full_playbook_check(Path("x.yml"), Path("/tmp"))
    assert not out.syntax_ok and not out.run_ok
    assert "syntax boom" in out.detail
    assert len(calls) == 1


def test_full_check_flags_failed_hosts(monkeypatch):
    fake, _ = _fake_run_factory([
        runner.CmdResult(0, "ok"),                       # syntax
        runner.CmdResult(2, RECAP),                      # run with a failure
    ])
    monkeypatch.setattr(runner, "run", fake)
    out = runner.full_playbook_check(Path("x.yml"), Path("/tmp"))
    assert out.syntax_ok and not out.run_ok


GOOD_FIRST = "PLAY RECAP ***\nnode1 : ok=3 changed=2 unreachable=0 failed=0\n"
GOOD_SECOND = "PLAY RECAP ***\nnode1 : ok=3 changed=0 unreachable=0 failed=0\n"
CHANGED_SECOND = "PLAY RECAP ***\nnode1 : ok=3 changed=1 unreachable=0 failed=0\n"


def test_full_check_idempotent_pass(monkeypatch):
    fake, calls = _fake_run_factory([
        runner.CmdResult(0, "ok"),
        runner.CmdResult(0, GOOD_FIRST),
        runner.CmdResult(0, GOOD_SECOND),
    ])
    monkeypatch.setattr(runner, "run", fake)
    out = runner.full_playbook_check(Path("x.yml"), Path("/tmp"))
    assert out.syntax_ok and out.run_ok and out.idempotent
    assert len(calls) == 3


def test_full_check_catches_non_idempotent(monkeypatch):
    fake, _ = _fake_run_factory([
        runner.CmdResult(0, "ok"),
        runner.CmdResult(0, GOOD_FIRST),
        runner.CmdResult(0, CHANGED_SECOND),
    ])
    monkeypatch.setattr(runner, "run", fake)
    out = runner.full_playbook_check(Path("x.yml"), Path("/tmp"))
    assert out.run_ok and not out.idempotent
    assert "changed=1" in out.detail


def test_run_handles_missing_binary():
    out = runner.run(["definitely-not-a-real-binary-xyz"])
    assert out.rc == 127 and not out.ok


def test_vault_extra_args_reach_the_command(monkeypatch):
    fake, calls = _fake_run_factory([runner.CmdResult(0, "ok")] * 3)
    monkeypatch.setattr(runner, "run", fake)
    runner.full_playbook_check(Path("x.yml"), Path("/tmp"),
                               extra_args=["--vault-password-file", "secret.txt"])
    assert "--vault-password-file" in calls[0]
