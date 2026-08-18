"""
Domain 1 tasks: ansible.cfg, ansible-navigator.yml and static inventories.
These are always the first things done on the real exam — everything else
depends on them.
"""

import random

from config import settings
from core.registry import TaskRegistry
from tasks.base import AnsibleTask
from validators import ansible_runner as runner


@TaskRegistry.register("ansible_config")
class AnsibleCfgTask(AnsibleTask):
    """Create the ansible.cfg every other task relies on."""

    def __init__(self):
        super().__init__("cfg_ansible_001", "ansible_config", "easy")

    def generate(self, **params):
        user = settings.REMOTE_USER
        self.params = {"user": user}
        self.description = f"""
Create an Ansible configuration file  {self.workdir}/ansible.cfg  so that:

  * the inventory file  {self.workdir}/inventory  is used by default
  * the remote user is  {user}
  * privilege escalation is enabled by default, via sudo, without
    prompting for a password
  * host key checking does not interrupt automation
"""
        self.hints = [
            "Sections: [defaults] for inventory/remote_user, [privilege_escalation] for become settings.",
            "Write it from scratch — it's ~6 lines. ansible-config init "
            "--disabled dumps EVERY setting, hundreds of lines commented "
            "out; only reach for it if you need something not covered here.",
            "Verify with: ansible-config dump --only-changed",
        ]
        self.exam_tips = ["Do this first on the real exam — every task after it depends on it."]
        return self

    def validate(self):
        res = self.result()
        if not self.check_exists(res, "ansible.cfg"):
            return res
        self.check_contains(res, "ansible.cfg", r"^\s*inventory\s*=.*inventory",
                            "ansible.cfg sets inventory")
        self.check_contains(res, "ansible.cfg",
                            rf"^\s*remote_user\s*=\s*{self.params['user']}",
                            "ansible.cfg sets remote_user")
        self.check_contains(res, "ansible.cfg", r"^\s*become\s*=\s*(true|yes)",
                            "privilege escalation enabled")
        return res


@TaskRegistry.register("ansible_config")
class NavigatorCfgTask(AnsibleTask):
    """ansible-navigator.yml — new emphasis in the RHEL 10 exam."""

    def __init__(self):
        super().__init__("cfg_navigator_001", "ansible_config", "medium")

    def generate(self, **params):
        self.description = f"""
Create an automation content navigator configuration file
{self.workdir}/ansible-navigator.yml  so that ansible-navigator:

  * runs in stdout mode rather than the interactive TUI
  * does not create playbook artifact files after each run
  * uses a pull policy of  missing , so it does not try to pull a new
    execution environment image on every run
"""
        self.hints = [
            "Top-level key is 'ansible-navigator:', then 'mode: stdout'.",
            "playbook-artifacts:  enable: false",
            "execution-environment:  pull:  policy: missing",
            "ansible-navigator --help-config lists every settable key.",
        ]
        self.exam_tips = [
            "Setting mode: stdout here saves you typing --mode stdout on "
            "every single command for the rest of the exam.",
            "A pull policy of 'always' on a machine with no registry access "
            "turns every navigator run into a long timeout.",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_exists(res, "ansible-navigator.yml"):
            return res
        self.check_contains(res, "ansible-navigator.yml", r"mode:\s*stdout",
                            "navigator runs in stdout mode")
        self.check_contains(res, "ansible-navigator.yml",
                            r"playbook-artifacts:[\s\S]{0,80}enable:\s*(false|no)",
                            "playbook artifacts disabled")
        self.check_contains(res, "ansible-navigator.yml",
                            r"policy:\s*missing",
                            "EE image pull policy is 'missing'")
        return res


@TaskRegistry.register("inventory")
class InventoryGroupsTask(AnsibleTask):
    """Static inventory with the classic exam group layout."""

    def __init__(self):
        super().__init__("inv_groups_001", "inventory", "easy")

    def generate(self, **params):
        nodes = self.nodes
        # Spread the available lab nodes over the exam-style groups.
        self.params = {
            "dev": nodes[0],
            "prod": nodes[1] if len(nodes) > 1 else nodes[0],
        }
        self.description = f"""
Create a static inventory file  {self.workdir}/inventory  that defines:

  * a group  dev   containing:  {self.params['dev']}
  * a group  prod  containing:  {self.params['prod']}
  * a group  webservers  containing the members of both dev and prod,
    declared as a children group rather than by repeating the hostnames

Every host must be reachable with  ansible webservers -m ping ."""
        self.hints = [
            "Children syntax: [webservers:children] with group names as lines.",
            "Verify structure with: ansible-inventory --graph",
            "A node that is the local machine needs "
            "ansible_connection=local to be reachable.",
        ]
        self.exam_tips = [
            "A children group is the difference between one edit and four "
            "when the host list changes. Graders look for the structure, "
            "not just the reachability.",
            "Keep dev and prod even after this task passes — several other "
            "tasks in this catalog assume both already exist.",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_exists(res, "inventory"):
            return res
        self.check_contains(res, "inventory", r"^\s*\[dev\]", "group dev defined")
        self.check_contains(res, "inventory", r"^\s*\[prod\]", "group prod defined")
        self.check_contains(res, "inventory", r"^\s*\[webservers:children\]",
                            "webservers is a children group")
        if runner.have_ansible():
            out = runner.run(["ansible-inventory", "--graph"], cwd=self.workdir)
            ok = out.ok and "@webservers" in out.stdout and self.params["dev"] in out.stdout
            res.add("ansible-inventory resolves the groups", ok,
                    "" if ok else out.text.strip()[-300:])
            self.check_node_state(res, "all webservers answer ping",
                                  "webservers", "ping", expect=r"\bpong\b")
        return res


@TaskRegistry.register("ansible_config")
class AnsibleCfgPerformanceTask(AnsibleTask):
    """The performance/safety half of ansible.cfg — forks, timeout and
    retry files — distinct from the inventory/become basics."""

    def __init__(self):
        super().__init__("cfg_performance_001", "ansible_config", "medium")

    def generate(self, **params):
        forks = params.get("forks") or random.choice([10, 15, 20])
        timeout = params.get("timeout") or random.choice([30, 45, 60])
        self.params = {"forks": forks, "timeout": timeout}
        self.description = f"""
Extend, or create,  {self.workdir}/ansible.cfg  so that under  [defaults] :

  * up to  {forks}  hosts are addressed in parallel
  * the per-task connection timeout is  {timeout}  seconds
  * no  .retry  files are written on failed runs
"""
        self.hints = [
            "[defaults] forks = " + str(forks),
            "[defaults] timeout = " + str(timeout),
            "[defaults] retry_files_enabled = False",
        ]
        self.exam_tips = [
            "forks defaults to 5 — on a larger host list that alone can be "
            "the difference between finishing a task and running out of time.",
            "ansible-config dump --only-changed shows what your file is "
            "actually setting, which is faster than re-reading it.",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_exists(res, "ansible.cfg"):
            return res
        self.check_contains(res, "ansible.cfg",
                            rf"^\s*forks\s*=\s*{self.params['forks']}",
                            "ansible.cfg sets forks")
        self.check_contains(res, "ansible.cfg",
                            rf"^\s*timeout\s*=\s*{self.params['timeout']}",
                            "ansible.cfg sets timeout")
        self.check_contains(res, "ansible.cfg",
                            r"^\s*retry_files_enabled\s*=\s*(false|no|0)",
                            "retry files are disabled")
        return res


@TaskRegistry.register("ansible_config")
class AnsibleCfgLoggingTask(AnsibleTask):
    """Persistent run logging via ansible.cfg — the difference between
    'what happened' living only in a scrollback buffer versus a file."""

    def __init__(self):
        super().__init__("cfg_logging_001", "ansible_config", "easy")

    def generate(self, **params):
        self.params = {"log_path": "ansible.log"}
        self.description = f"""
Extend, or create,  {self.workdir}/ansible.cfg  so that every
ansible-playbook  run appends a full log to
{self.workdir}/{self.params['log_path']} .

Then run any playbook, or an ad-hoc ping, so that the log file receives
content."""
        self.hints = [
            "[defaults] log_path = ./ansible.log",
            "log_path only takes effect for runs started AFTER it's set — "
            "run something after editing ansible.cfg, not before.",
        ]
        self.exam_tips = [
            "A log_path is worth setting on exam day for yourself: when a "
            "play half-worked twenty minutes ago, the log still has the "
            "output your scrollback lost.",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_exists(res, "ansible.cfg"):
            return res
        self.check_contains(res, "ansible.cfg",
                            rf"^\s*log_path\s*=.*{self.params['log_path']}",
                            "ansible.cfg sets log_path")
        if runner.have_ansible():
            runner.run(["ansible", "all", "-m", "ping"], cwd=self.workdir)
            log_file = self.workdir / self.params["log_path"]
            has_content = log_file.exists() and log_file.stat().st_size > 0
            res.add(f"{self.params['log_path']} received log output", has_content,
                    "" if has_content else
                    "run an ansible command after setting log_path")
        return res


@TaskRegistry.register("inventory")
class YamlInventoryTask(AnsibleTask):
    """The exam may specify either inventory syntax — YAML is the more
    modern, more structured alternative to the classic INI layout."""

    def __init__(self):
        super().__init__("inv_yaml_001", "inventory", "medium")

    def generate(self, **params):
        nodes = self.nodes
        self.params = {"staging": nodes[0]}
        self.description = f"""
Create a static inventory file  {self.workdir}/inventory.yml  in YAML
format, not INI, that defines:

  * a group  staging  containing:  {self.params['staging']}
  * that host carrying the variable  ansible_connection: local  inline
    in the YAML

Point the  inventory =  setting in  {self.workdir}/ansible.cfg  at
inventory.yml  so it becomes the active inventory."""
        self.hints = [
            "YAML inventory structure: all: children: staging: hosts: "
            "<hostname>: <vars...>",
            "Indentation is everything here — a misplaced host under the "
            "wrong group is the #1 way this goes wrong.",
            "ansible.cfg: inventory = ./inventory.yml",
            "Check the result with: ansible-inventory --graph",
        ]
        self.exam_tips = [
            "The exam can specify either syntax, and a YAML inventory is "
            "the one people fumble because the nesting is load-bearing: "
            "all -> children -> <group> -> hosts -> <host>.",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_exists(res, "inventory.yml"):
            return res
        self.check_contains(res, "inventory.yml", r"^\s*staging\s*:",
                            "inventory.yml defines a staging group")
        self.check_contains(res, "inventory.yml",
                            self.params["staging"], "staging host present")
        self.check_contains(res, "ansible.cfg", r"inventory\s*=.*inventory\.yml",
                            "ansible.cfg points at inventory.yml")
        if runner.have_ansible():
            out = runner.run(["ansible-inventory", "--graph"], cwd=self.workdir)
            ok = out.ok and "@staging" in out.stdout
            res.add("ansible-inventory resolves the YAML inventory", ok,
                    "" if ok else out.text.strip()[-300:])
        return res


@TaskRegistry.register("inventory")
class InventoryHostVarsTask(AnsibleTask):
    """Per-host variables declared directly in the inventory — the
    lightweight alternative to a host_vars/ directory for one-off values."""

    def __init__(self):
        super().__init__("inv_hostvars_001", "inventory", "easy")

    def generate(self, **params):
        nodes = self.nodes
        target = nodes[0]
        port = "2222"
        self.params = {"target": target, "port": port}
        self.description = f"""
In the inventory file  {self.workdir}/inventory , give the host  {target}
the inline host variable:

    ansible_port={port}

It must resolve for that host under  ansible-inventory --host {target} ."""
        self.hints = [
            "INI-style inline host vars: <hostname> ansible_port=2222 "
            "key=value key2=value2 on the SAME line as the hostname.",
            "ansible-inventory --host <name> prints that host's resolved "
            "variables as JSON — the fastest way to confirm a var actually "
            "took effect.",
        ]
        self.exam_tips = [
            "Inline host vars are for one-off values. Once a host needs "
            "more than a couple, host_vars/<hostname>.yml is the form that "
            "stays readable.",
            "This records a non-standard SSH port; the port does not have "
            "to be listening for the inventory entry to be correct.",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_exists(res, "inventory"):
            return res
        self.check_contains(res, "inventory",
                            rf"{self.params['target']}\s+.*ansible_port={self.params['port']}",
                            f"{self.params['target']} has an inline ansible_port var")
        if runner.have_ansible():
            out = runner.run(["ansible-inventory", "--host", self.params["target"]],
                             cwd=self.workdir)
            ok = out.ok and self.params["port"] in out.stdout
            res.add("ansible-inventory --host resolves the variable", ok,
                    "" if ok else out.text.strip()[-300:])
        return res
