"""Domain 6: Ansible Vault."""

import random

from core.registry import TaskRegistry
from tasks.base import AnsibleTask
from validators import ansible_runner as runner


@TaskRegistry.register("vault")
class VaultFileTask(AnsibleTask):
    def __init__(self):
        super().__init__("vault_file_001", "vault", "easy")

    def generate(self, **params):
        password = params.get("password") or random.choice(
            ["P@ssw0rd", "r3dh4t123", "wh3n2use"])
        self.params = {"password": password,
                       "vars": ["pw_developer", "pw_manager"]}
        self.description = f"""
In your working directory ({self.workdir}):

  1. Create a vault password file  secret.txt  containing the single
     line:   {password}
  2. Create an ENCRYPTED variable file  vault.yml , encrypted with that
     password file, defining two variables (any values):
        pw_developer
        pw_manager

ansible-vault view --vault-password-file secret.txt vault.yml
must show both variables.
"""
        self.hints = [
            "ansible-vault create --vault-password-file secret.txt vault.yml",
            "Already have a plaintext file? ansible-vault encrypt it.",
        ]
        return self

    def validate(self):
        res = self.result()
        if not (self.check_exists(res, "secret.txt") &
                self.check_exists(res, "vault.yml")):
            return res
        self.check_contains(res, "vault.yml", r"^\$ANSIBLE_VAULT;",
                            "vault.yml is vault-encrypted")
        if runner.have_ansible():
            out = runner.vault_view(self.workdir / "vault.yml",
                                    self.workdir / "secret.txt", self.workdir)
            res.add("vault decrypts with secret.txt", out.ok,
                    "" if out.ok else out.text.strip()[-200:])
            if out.ok:
                for var in self.params["vars"]:
                    res.add(f"vault defines {var}", var in out.stdout,
                            "" if var in out.stdout else f"{var} missing")
        return res


@TaskRegistry.register("vault")
class VaultedUsersTask(AnsibleTask):
    def __init__(self):
        super().__init__("vault_users_001", "vault", "hard")

    def generate(self, **params):
        users = params.get("users") or random.sample(
            ["natasha", "harry", "fred", "sarah", "amr"], 2)
        self.params = {"users": users}
        listing = "\n".join(f"        - {u}" for u in users)
        self.description = f"""
Combine vault + user management (a classic exam pairing). In your working
directory ({self.workdir}):

  1. Reuse (or create) the encrypted  vault.yml  with password file
     secret.txt , defining  pw_developer  as the password value.
  2. Create a variables file  user_list.yml  defining:
        users:
{listing}
  3. Create a playbook  create_users.yml  that loads both files with
     vars_files and creates each user on ALL managed nodes with:
        * supplementary group  devops_group  (create it too)
        * password set from  pw_developer  (properly hashed!)

Run it with:  ansible-playbook --vault-password-file secret.txt create_users.yml
"""
        self.hints = [
            "password: \"{{ pw_developer | password_hash('sha512') }}\"",
            "user module: groups: devops_group, append: true.",
            "A raw string in password: is NOT a valid hash — login would break.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "create_users.yml", r"vars_files:",
                            "playbook loads variable files")
        self.check_contains(res, "create_users.yml", r"password_hash",
                            "password is hashed with a filter")
        if not self.check_playbook_runs(
                res, "create_users.yml",
                extra_args=["--vault-password-file", "secret.txt"]):
            return res
        for user in self.params["users"]:
            self.check_node_state(res, f"user {user} exists in devops_group",
                                  "all", "ansible.builtin.command",
                                  f"id {user}", expect=r"devops_group",
                                  become=True)
        return res
