import pytest


@pytest.fixture(autouse=True)
def _no_lab_autodetect(monkeypatch):
    """Tests must never depend on the host's real docker/vagrant state
    (CLAUDE.md: no Ansible, nodes, or root). Without this, settings.get_nodes()
    would shell out to `docker ps` / `vagrant status` and, on a machine that
    happens to have a lab running, silently swap "localhost" for real node
    names mid-test-suite."""
    from config import settings
    monkeypatch.setattr(settings, "_detect_lab_nodes", lambda: [])
    monkeypatch.setattr(settings, "_detected_nodes_cache", None)


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
