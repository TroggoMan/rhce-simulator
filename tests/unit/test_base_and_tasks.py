"""Static-layer tests for the base class and every task in the catalog."""

import pytest

from core.registry import TaskRegistry
from core.validator import ValidationResult
from tasks.environment import AnsibleCfgTask
from tasks.vault import VaultFileTask


def test_validation_result_scoring():
    res = ValidationResult(task_id="t", max_score=20)
    assert not res.passed and res.score == 0        # no checks = no pass
    res.add("a", True).add("b", True)
    assert res.passed and res.score == 20
    res.add("c", False)
    assert not res.passed and res.score == 13       # 2/3 of 20, rounded


def test_check_exists_and_contains(workdir):
    task = AnsibleCfgTask().generate()
    res = task.result()
    assert not task.check_exists(res, "ansible.cfg")
    (workdir / "ansible.cfg").write_text(
        "[defaults]\ninventory = ./inventory\nremote_user = devops\n"
        "[privilege_escalation]\nbecome = true\n")
    res2 = task.validate()
    assert res2.passed, [c for c in res2.checks if not c.passed]


def test_vault_static_checks(workdir, no_ansible):
    task = VaultFileTask().generate()
    (workdir / "secret.txt").write_text(task.params["password"] + "\n")
    (workdir / "vault.yml").write_text("$ANSIBLE_VAULT;1.1;AES256\n61626364\n")
    res = task.validate()
    names = {c.name: c.passed for c in res.checks}
    assert names["vault.yml is vault-encrypted"]
    assert names["secret.txt exists"]


@pytest.mark.parametrize("task_class", TaskRegistry.all_task_classes(),
                         ids=lambda tc: tc.__name__)
def test_every_task_generates_and_validates_safely(task_class, workdir, no_ansible):
    """Every task must produce a real description and survive validation
    against an empty working directory without raising (all failed checks,
    never an exception)."""
    task = task_class().generate()
    assert task.id and task.category
    assert len(task.description.strip()) > 60, "description too thin"
    assert task.hints, f"{task.id} has no hints"
    assert task.points > 0 and task.exam_domain in range(1, 12)

    res = task.validate()
    assert isinstance(res, ValidationResult)
    assert not res.passed, "empty workdir must never pass"
    assert res.checks, "validation must report at least one check"


def test_generate_is_deterministic_with_params(workdir):
    t1 = AnsibleCfgTask().generate()
    t2 = AnsibleCfgTask().generate()
    assert t1.params == t2.params  # cfg task has fixed params
