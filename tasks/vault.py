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
In  {self.workdir} :

  1. Create a vault password file  secret.txt  containing the single
     line:   {password}
  2. Create an ENCRYPTED variable file  vault.yml , encrypted with that
     password file, defining two variables (any values):
        pw_developer
        pw_manager

ansible-vault view --vault-password-file secret.txt vault.yml must show
both variables."""
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
Combine vault + user management (a classic exam pairing). In
{self.workdir} :

  1. Reuse (or create) the encrypted  vault.yml  with password file
     secret.txt , defining  pw_developer  as the password value.
  2. Create a variables file  user_list.yml  defining:
        users:
{listing}
  3. Create a playbook  create_users.yml  that loads both files with
     vars_files and creates each user on ALL managed nodes with:
        * supplementary group  devops_group  (create it too)
        * password set from  pw_developer  (properly hashed!)

Run it with:  ansible-playbook --vault-password-file secret.txt
create_users.yml"""
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


@TaskRegistry.register("vault")
class VaultEncryptStringTask(AnsibleTask):
    """encrypt_string: an inline vaulted value living directly in a
    playbook — no separate vault file at all."""

    def __init__(self):
        super().__init__("vault_encrypt_string_001", "vault", "medium")

    def generate(self, **params):
        password = params.get("password") or random.choice(
            ["Str0ngS3cret!", "Inl1neVault#"])
        self.params = {"password": password, "var_name": "api_token"}
        self.description = f"""
In  {self.workdir} :

  1. Create a vault password file  secret.txt  containing the single
     line:   {password}
  2. Use  ansible-vault encrypt_string  to produce an INLINE encrypted
     value for a variable named  {self.params['var_name']}  (value can be
     anything, e.g. a fake API token) — encrypted with  secret.txt .
  3. Paste that encrypted block directly into a playbook
     encrypt_string.yml  as the value of a  vars:  entry (NOT a separate
     vars_files: — the ciphertext lives INSIDE the playbook YAML), then
     have a task write  {{{{ {self.params['var_name']} }}}}  to
     /root/token.txt  on ALL managed nodes.

ansible-playbook --vault-password-file secret.txt encrypt_string.yml must
run cleanly and produce the decrypted value in /root/token.txt."""
        self.hints = [
            "ansible-vault encrypt_string --vault-password-file secret.txt "
            f"'<value>' --name '{self.params['var_name']}'",
            "The command's output is valid YAML on its own — paste it "
            "directly under vars: in the playbook, indentation intact.",
            "Unlike a vault FILE, encrypt_string output starts with "
            "'!vault |' inline, right where the variable is used.",
        ]
        self.exam_tips = [
            "Not every secret deserves its own file. encrypt_string puts a "
            "single encrypted value inline in an otherwise readable vars "
            "file, so the rest of the file stays reviewable in git.",
            "encrypt_string is for ONE secret value living alongside "
            "non-secret playbook content in the same file — reach for a "
            "full vault FILE instead when most of a vars file needs "
            "protecting.",
        ]
        return self

    def validate(self):
        res = self.result()
        if not (self.check_exists(res, "secret.txt") and
                self.check_exists(res, "encrypt_string.yml")):
            return res
        self.check_contains(res, "encrypt_string.yml", r"!vault\s*\|",
                            "playbook contains an inline !vault value")
        self.check_contains(res, "encrypt_string.yml",
                            rf"{self.params['var_name']}\s*:\s*!vault",
                            f"the vaulted value is assigned to {self.params['var_name']}")
        if not self.check_playbook_runs(
                res, "encrypt_string.yml",
                extra_args=["--vault-password-file", "secret.txt"]):
            return res
        self.check_node_state(res, "/root/token.txt holds the decrypted value",
                              "all", "ansible.builtin.command",
                              "cat /root/token.txt", become=True)
        return res


@TaskRegistry.register("vault")
class VaultRekeyTask(AnsibleTask):
    """Key rotation: changing a vault's password without touching its
    plaintext content — a real operational skill, not just encrypt/decrypt."""

    def __init__(self):
        super().__init__("vault_rekey_001", "vault", "medium")

    def generate(self, **params):
        old_pw = params.get("old_pw") or "OldVaultPass1"
        new_pw = params.get("new_pw") or "RotatedVaultPass2"
        self.params = {"old_pw": old_pw, "new_pw": new_pw,
                       "old_file": "old_secret.txt", "new_file": "new_secret.txt",
                       "var": "rotated_value"}
        self.description = f"""
A vault password has been compromised and must be rotated.

In  {self.workdir} :

  1. Create  {self.params['old_file']}  containing:  {old_pw}
  2. Create an encrypted  rotate_vault.yml  (password from
     {self.params['old_file']} ) defining one variable:
        {self.params['var']}: "some secret value"
  3. Create  {self.params['new_file']}  containing:  {new_pw}
  4. REKEY  rotate_vault.yml  from the old password to the new one — do
     NOT just decrypt-and-re-encrypt by hand; use ansible-vault rekey.

After rekeying,  {self.params['old_file']}  must no longer decrypt the
file; ONLY  {self.params['new_file']}  may."""
        self.hints = [
            f"ansible-vault create --vault-password-file {self.params['old_file']} rotate_vault.yml",
            f"ansible-vault rekey --vault-password-file {self.params['old_file']} "
            f"--new-vault-password-file {self.params['new_file']} rotate_vault.yml",
            "rekey re-encrypts in place with a new password/cipher without "
            "you ever seeing the plaintext yourself.",
        ]
        return self

    def validate(self):
        res = self.result()
        if not (self.check_exists(res, "rotate_vault.yml") and
                self.check_exists(res, self.params["new_file"])):
            return res
        self.check_contains(res, "rotate_vault.yml", r"^\$ANSIBLE_VAULT;",
                            "rotate_vault.yml is vault-encrypted")
        if not runner.have_ansible():
            return res
        new_out = runner.vault_view(self.workdir / "rotate_vault.yml",
                                    self.workdir / self.params["new_file"],
                                    self.workdir)
        res.add("the file decrypts with the NEW password", new_out.ok,
                "" if new_out.ok else new_out.text.strip()[-200:])
        if new_out.ok:
            res.add(f"decrypted content still defines {self.params['var']}",
                    self.params["var"] in new_out.stdout,
                    "" if self.params["var"] in new_out.stdout else
                    f"{self.params['var']} missing after rekey")
        if self.check_exists(res, self.params["old_file"]):
            old_out = runner.vault_view(self.workdir / "rotate_vault.yml",
                                        self.workdir / self.params["old_file"],
                                        self.workdir)
            res.add("the OLD password no longer works (real rotation happened)",
                    not old_out.ok,
                    "" if not old_out.ok else
                    "the old password file still decrypts the vault — it "
                    "was not actually rekeyed")
        return res
