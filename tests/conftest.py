import pytest


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """Point the simulator at a throwaway Ansible working directory."""
    monkeypatch.setenv("RHCE_SIM_WORKDIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def no_ansible(monkeypatch):
    """Pretend ansible-core is not installed (pure static grading)."""
    from validators import ansible_runner
    monkeypatch.setattr(ansible_runner, "have_ansible", lambda: False)
    monkeypatch.setattr(ansible_runner, "have_navigator", lambda: False)
