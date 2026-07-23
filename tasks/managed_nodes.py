"""
Domain 4: configuring managed nodes — SSH key distribution and privilege
escalation. Almost always the first real task on exam day, since everything
after it depends on working access. (Privilege escalation itself is drilled
by the Users & Groups Automation category's sudoers task; this task focuses
on the key-distribution half, since the lab's baseline SSH access is set up
for you by scripts/lab-setup.sh and can't be re-tested directly — instead
you distribute a SECOND, freshly-generated key and the grader independently
proves it works.)
"""

from config import settings
from core.registry import TaskRegistry
from tasks.base import AnsibleTask
from validators import ansible_runner as runner


@TaskRegistry.register("managed_nodes")
class SshKeyDistributionTask(AnsibleTask):
    def __init__(self):
        super().__init__("mn_ssh_key_001", "managed_nodes", "medium")

    def generate(self, **params):
        self.params = {"key": "keys/id_rhce_practice", "user": settings.REMOTE_USER}
        self.description = f"""
Generate a NEW SSH keypair for automation purposes (do not reuse the lab's
existing key) in your working directory ({self.workdir}):

    mkdir -p keys && ssh-keygen -t ed25519 -N "" -f {self.params['key']}

Then create a playbook  distribute_key.yml  that, using your EXISTING
working access, distributes the NEW public key
({self.params['key']}.pub) into the  {self.params['user']}  user's
authorized_keys on ALL managed nodes. Use the  authorized_key  module —
not a hand-edited file, not ssh-copy-id.

You don't need to prove the new key works yourself — validation connects
with it independently. Idempotent.
"""
        self.hints = [
            "ansible.posix.authorized_key: user: {}, key: \"{{{{ lookup('file', "
            "'{}.pub') }}}}\"".format(self.params['user'], self.params['key']),
            "lookup('file', ...) reads the local pubkey at playbook-run time — "
            "no need to paste the key text into the playbook.",
        ]
        self.exam_tips = [
            "On the real exam this is usually task 1 — you're given root or "
            "password access and expected to set up key-based access and "
            "passwordless sudo yourself before anything else will run "
            "unattended. Passwordless sudo itself is drilled separately by "
            "the Users & Groups Automation category.",
        ]
        return self

    def validate(self):
        res = self.result()
        key_path = self.workdir / self.params["key"]
        pub_path = self.workdir / f"{self.params['key']}.pub"
        res.add(f"{self.params['key']} and .pub exist",
                key_path.exists() and pub_path.exists(),
                "" if key_path.exists() and pub_path.exists() else
                f"generate with: ssh-keygen -t ed25519 -N '' -f {self.params['key']}")
        self.check_contains(res, "distribute_key.yml",
                            r"authorized_key\s*:|ansible\.posix\.authorized_key",
                            "playbook uses the authorized_key module")
        if not self.check_playbook_runs(res, "distribute_key.yml"):
            return res
        if runner.have_ansible() and key_path.exists():
            out = runner.run(
                ["ansible", "all", "-m", "ping", "--private-key", str(key_path),
                 "-u", self.params["user"]],
                cwd=self.workdir)
            ok = out.ok and "pong" in out.stdout
            res.add("new key independently grants access to all nodes", ok,
                    "" if ok else out.text.strip()[-300:])
        return res
