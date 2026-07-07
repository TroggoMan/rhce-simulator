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
