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
Create an Ansible configuration file  ansible.cfg  in your working
directory ({self.workdir}) so that:

  * the inventory file  ./inventory  in the same directory is used by default
  * the remote user is  {user}
  * privilege escalation is enabled by default (become, via sudo, without
    prompting for a password)
  * host key checking does not interrupt automation
"""
        self.hints = [
            "Sections: [defaults] for inventory/remote_user, [privilege_escalation] for become settings.",
            "ansible-config init --disabled gives you a fully commented reference file.",
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
ansible-navigator.yml  in your working directory ({self.workdir}) so that
ansible-navigator:

  * runs in stdout mode (plain ansible-playbook-style output, no TUI)
  * does not create playbook artifact files after each run
  * does not try to pull a new execution environment image on every run
    (pull policy: missing)
"""
        self.hints = [
            "Top-level key is 'ansible-navigator:', then 'mode: stdout'.",
            "playbook-artifacts:  enable: false",
            "execution-environment:  pull:  policy: missing",
            "Reference: ansible-navigator settings documentation (ansible-navigator --help-config).",
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
Create a static inventory file  ./inventory  in your working directory
({self.workdir}) that defines:

  * a group  dev   containing:  {self.params['dev']}
  * a group  prod  containing:  {self.params['prod']}
  * a group  webservers  that contains the members of BOTH dev and prod
    (use a children group, do not repeat the hostnames)

All hosts must be reachable with  ansible webservers -m ping .
(If a node is the local machine, set  ansible_connection=local  on it.)
"""
        self.hints = [
            "Children syntax: [webservers:children] with group names as lines.",
            "Verify structure with: ansible-inventory --graph",
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
Extend (or create) an  ansible.cfg  in your working directory
({self.workdir}) with performance and hygiene settings, under
[defaults] :

  * run up to  {forks}  hosts in parallel (forks)
  * a per-task connection timeout of  {timeout}  seconds
  * do NOT write  .retry  files on failed runs (they're clutter and
    almost never actually used to re-run just the failed hosts)
"""
        self.hints = [
            "[defaults] forks = " + str(forks),
            "[defaults] timeout = " + str(timeout),
            "[defaults] retry_files_enabled = False",
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
Extend (or create) an  ansible.cfg  in your working directory
({self.workdir}) so that every  ansible-playbook  run appends a full log
to  {self.params['log_path']}  in the same directory (under [defaults]).

Then run ANY playbook (or a trivial ad-hoc ping) and confirm the log file
actually receives content.
"""
        self.hints = [
            "[defaults] log_path = ./ansible.log",
            "log_path only takes effect for runs started AFTER it's set — "
            "run something after editing ansible.cfg, not before.",
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
Create a static inventory file  inventory.yml  (YAML format, NOT INI) in
your working directory ({self.workdir}) that defines:

  * a group  staging  containing:  {self.params['staging']}
  * that host given the variable  ansible_connection: local  directly
    inline in the YAML (only if it needs it to be reachable — set it
    regardless, it's harmless if unused)

Point ansible.cfg's  inventory =  at  inventory.yml  (not the old INI
file) so this becomes the active inventory. Verify with
ansible-inventory --graph .
"""
        self.hints = [
            "YAML inventory structure: all: children: staging: hosts: "
            "<hostname>: <vars...>",
            "Indentation is everything here — a misplaced host under the "
            "wrong group is the #1 way this goes wrong.",
            "ansible.cfg: inventory = ./inventory.yml",
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
In your existing (or a new) inventory file  ./inventory  in your working
directory ({self.workdir}), give the host  {target}  an inline
host variable:

    ansible_port={port}

(This documents a non-standard SSH port for that host — the value itself
doesn't need to actually work if the real lab uses the default port; the
inventory syntax is what's graded.)

Confirm it resolves with:  ansible-inventory --host {target}
"""
        self.hints = [
            "INI-style inline host vars: <hostname> ansible_port=2222 "
            "key=value key2=value2 on the SAME line as the hostname.",
            "ansible-inventory --host <name> prints that host's resolved "
            "variables as JSON — the fastest way to confirm a var actually "
            "took effect.",
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
