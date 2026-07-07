"""Domain 7: users, groups and sudo automation."""

import random

from core.registry import TaskRegistry
from tasks.base import AnsibleTask


@TaskRegistry.register("users_auto")
class UsersFromVarsTask(AnsibleTask):
    def __init__(self):
        super().__init__("users_vars_001", "users_auto", "hard")

    def generate(self, **params):
        pool = [("amr", "developer"), ("lisa", "developer"),
                ("pete", "manager"), ("dana", "manager")]
        chosen = params.get("users") or random.sample(pool, 3)
        self.params = {"users": chosen}
        listing = "\n".join(
            f"          - name: {n}\n            job: {j}" for n, j in chosen)
        self.description = f"""
Data-driven user management. In your working directory ({self.workdir}):

  1. Create a variables file  vars/users_vars.yml  defining:

        users:
{listing}

  2. Create a playbook  users.yml  that loads it and, on ALL managed
     nodes, creates ONLY the users whose  job  is  developer , with:
        * supplementary group  developer_group  (create it, GID 3500)
        * shell /bin/bash

     Users with other jobs must NOT be created by this playbook.

Idempotent.
"""
        self.hints = [
            "loop: \"{{ users }}\" with when: item.job == 'developer'.",
            "group module before user module; user: groups: + append: true.",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_exists(res, "vars/users_vars.yml"):
            return res
        self.check_contains(res, "users.yml", r"when:.*job|job.*==",
                            "playbook filters on the job field")
        if not self.check_playbook_runs(res, "users.yml"):
            return res
        for name, job in self.params["users"]:
            if job == "developer":
                self.check_node_state(res, f"developer {name} in developer_group",
                                      "all", "ansible.builtin.command",
                                      f"id {name}", expect="developer_group",
                                      become=True)
            else:
                self.check_node_state(res, f"non-developer {name} NOT created",
                                      "all", "ansible.builtin.shell",
                                      f"id {name} && echo EXISTS || echo ABSENT",
                                      expect="ABSENT", become=True)
        return res


@TaskRegistry.register("users_auto")
class SudoersGroupTask(AnsibleTask):
    def __init__(self):
        super().__init__("users_sudo_001", "users_auto", "medium")

    def generate(self, **params):
        group = params.get("group") or random.choice(["opsadmin", "sysops"])
        self.params = {"group": group}
        self.description = f"""
Create a playbook  sudo_group.yml  in your working directory
({self.workdir}) that, on ALL managed nodes:

  * creates the group  {group}
  * deploys  /etc/sudoers.d/{group}  granting members of that group
    passwordless sudo for ALL commands:
        %{group} ALL=(ALL) NOPASSWD: ALL
  * the sudoers file must be validated before being put in place
    (a broken sudoers file can lock you out of every node at once)

Idempotent.
"""
        self.hints = [
            "copy (or template) supports validate: 'visudo -cf %s'.",
            "Mode 0440 is the sudoers convention.",
        ]
        return self

    def validate(self):
        res = self.result()
        group = self.params["group"]
        self.check_contains(res, "sudo_group.yml", r"validate:",
                            "sudoers deployed with validation")
        if not self.check_playbook_runs(res, "sudo_group.yml"):
            return res
        self.check_node_state(res, f"group {group} exists", "all",
                              "ansible.builtin.command", f"getent group {group}",
                              expect=group, become=True)
        self.check_node_state(res, f"sudoers drop-in valid and in place", "all",
                              "ansible.builtin.command",
                              f"visudo -cf /etc/sudoers.d/{group}",
                              expect=r"parsed OK", become=True)
        return res
