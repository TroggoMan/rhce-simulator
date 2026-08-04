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
        * a LOCKED password (these accounts are for key-based access only,
          so no password login is possible)

     Users with other jobs must NOT be created by this playbook.

Idempotent.
"""
        self.hints = [
            "loop: \"{{ users }}\" with when: item.job == 'developer'.",
            "group module before user module; user: groups: + append: true.",
            "password_lock: true locks the account's password field — it is "
            "not the same as omitting password:, which leaves the account "
            "with no password entry at all.",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_exists(res, "vars/users_vars.yml"):
            return res
        self.check_contains(res, "users.yml", r"when:.*job|job.*==",
                            "playbook filters on the job field")
        self.check_contains(res, "users.yml", r"password_lock:\s*(true|yes)",
                            "created accounts have a locked password")
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


@TaskRegistry.register("users_auto")
class UserSshKeyGenTask(AnsibleTask):
    """The user module's OWN key-generation option — different from
    managed_nodes' authorized_key task, which distributes a key generated
    on the control node. Here the KEY is generated ON the managed node."""

    def __init__(self):
        super().__init__("users_sshkeygen_001", "users_auto", "medium")

    def generate(self, **params):
        name = params.get("name") or random.choice(["deployer", "svc_ansible"])
        self.params = {"name": name}
        self.description = f"""
Create a playbook  user_sshkey.yml  in your working directory
({self.workdir}) that, on ALL managed nodes:

  * ensures the user  {name}  exists, with a home directory
  * generates an ed25519 SSH keypair FOR that user, ON that node (not on
    the control node), using the  user  module's own key-generation
    option — no separate ssh-keygen shell command

The key must end up at  /home/{name}/.ssh/id_ed25519  (and its .pub)
on every node. Idempotent — a second run must not regenerate the key.
"""
        self.hints = [
            "ansible.builtin.user: generate_ssh_key: true, "
            "ssh_key_type: ed25519, ssh_key_file: .ssh/id_ed25519",
            "The user module only generates a key if one doesn't already "
            "exist at that path — that's what makes this idempotent for "
            "free.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "user_sshkey.yml", r"generate_ssh_key:\s*(true|yes)",
                            "playbook uses generate_ssh_key on the user module")
        if not self.check_playbook_runs(res, "user_sshkey.yml"):
            return res
        priv = f"/home/{self.params['name']}/.ssh/id_ed25519"
        self.check_node_state(res, f"{priv} exists", "all",
                              "ansible.builtin.command", f"test -f {priv}",
                              become=True)
        self.check_node_state(res, f"{priv}.pub exists", "all",
                              "ansible.builtin.command", f"test -f {priv}.pub",
                              become=True)
        return res


@TaskRegistry.register("users_auto")
class UserRemovalTask(AnsibleTask):
    """Decommissioning: state: absent, remove: yes — the opposite skill
    from every other users_auto task, and just as commonly graded."""

    def __init__(self):
        super().__init__("users_removal_001", "users_auto", "easy")

    def generate(self, **params):
        name = params.get("name") or random.choice(["oldadmin", "tempcontractor"])
        self.params = {"name": name}
        self.description = f"""
An account is being decommissioned. Create a playbook  user_removal.yml
in your working directory ({self.workdir}) that, on ALL managed nodes:

  1. FIRST ensures the user  {name}  exists (so there's something to
     remove — simulates the account already being present)
  2. THEN removes it completely: the account AND its home directory

Both steps live in the same playbook, in order. (Because step 1 recreates
the account on every run just before step 2 deletes it again, this
particular playbook legitimately reports changed on every run — that's
not a bug to chase here; the removal LOGIC is what's graded.)
"""
        self.hints = [
            "Two user tasks: first state: present to create it, then "
            "state: absent, remove: true to delete it — same module, "
            "opposite state.",
            "remove: true is what deletes the home directory and mail "
            "spool; state: absent alone only removes the account entry.",
        ]
        self.exam_tips = [
            "state: absent WITHOUT remove: true leaves the home directory "
            "behind — a half-decommissioned account is a common way to "
            "lose points on this exact task type.",
        ]
        return self

    def validate(self):
        res = self.result()
        name = self.params["name"]
        self.check_contains(res, "user_removal.yml", r"state:\s*absent",
                            "playbook removes the user (state: absent)")
        self.check_contains(res, "user_removal.yml", r"remove:\s*(true|yes)",
                            "removal also deletes the home directory (remove: true)")
        if not self.check_playbook_runs(res, "user_removal.yml",
                                        require_idempotent=False):
            return res
        self.check_node_state(res, f"{name} no longer exists", "all",
                              "ansible.builtin.shell",
                              f"id {name} && echo EXISTS || echo GONE",
                              expect=r"GONE", become=True)
        self.check_node_state(res, f"/home/{name} was removed", "all",
                              "ansible.builtin.shell",
                              f"test -d /home/{name} && echo LEFTOVER || echo CLEAN",
                              expect=r"CLEAN", become=True)
        return res
