"""
Domain 4: configuring managed nodes — SSH key distribution and privilege
escalation. Almost always the first real task on exam day, since everything
after it depends on working access.

The lab scripts (lab-setup.sh, vm-lab-setup.sh) deliberately hand you
nothing but root + a password on each node — no inventory, no automation
user, no key. Bootstrapping THAT into a real inventory/ansible.cfg/user/key
setup is genuine, ungraded groundwork every candidate has to do by hand
first (see --learn managed_nodes for the exact -k/-K bootstrap sequence);
it can't be graded here because grading itself needs a working config to
run playbooks and ad-hoc queries against — chicken, egg. Once that's done,
SshKeyDistributionTask below drills a distinct, later skill: distributing
an ADDITIONAL key (a second admin, a CI credential, a rotation) onto a
setup that already works, which is what the grader can independently
verify. Privilege escalation itself is drilled by the Users & Groups
Automation category's sudoers task.
"""

import re

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
You've already bootstrapped your OWN working Ansible access to these
nodes (see --learn managed_nodes if not — this task assumes it exists).
Now a second admin/CI credential needs access too.

Generate a NEW SSH keypair in your working directory ({self.workdir}):

    mkdir -p keys && ssh-keygen -t ed25519 -N "" -f {self.params['key']}

Then create a playbook  distribute_key.yml  that, using your EXISTING
working access, distributes THAT NEW public key
({self.params['key']}.pub) into the  {self.params['user']}  user's
authorized_keys on ALL managed nodes — ADDING it, not replacing your own.
Use the  authorized_key  module — not a hand-edited file, not ssh-copy-id.

You don't need to prove the new key works yourself — validation connects
with it independently. Idempotent.
"""
        self.hints = [
            "ansible.posix.authorized_key: user: {}, key: \"{{{{ lookup('file', "
            "'{}.pub') }}}}\"".format(self.params['user'], self.params['key']),
            "lookup('file', ...) reads the local pubkey at playbook-run time — "
            "no need to paste the key text into the playbook.",
            "authorized_key APPENDS by default — it doesn't wipe out your "
            "own key just because you're adding another one.",
        ]
        self.exam_tips = [
            "This drills the SECOND key you add to an already-working "
            "setup — the FIRST one (getting from root/password to your own "
            "key-based access at all) is the ungraded bootstrap step every "
            "candidate does by hand; see --learn managed_nodes for that "
            "sequence. Passwordless sudo itself is drilled separately by "
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


@TaskRegistry.register("managed_nodes")
class PrivilegeEscalationConfigTask(AnsibleTask):
    """Per-GROUP privilege escalation via group_vars — distinct from
    ansible.cfg's global become settings, and from the sudoers file itself."""

    def __init__(self):
        super().__init__("mn_become_config_001", "managed_nodes", "medium")

    def generate(self, **params):
        self.params = {"group": "restricted", "become_user": "appsvc",
                       "marker": "/var/tmp/restricted_ran_as_appsvc"}
        self.description = f"""
Not every group should escalate to root. In your working directory
({self.workdir}):

  1. Ensure your inventory has (or add) a group named
     {self.params['group']}  containing at least one managed node.
  2. Create  group_vars/{self.params['group']}.yml  configuring
     privilege escalation FOR THAT GROUP ONLY to become the user
     {self.params['become_user']}  (not root) via sudo.
  3. Create a playbook  become_config.yml  that, targeting the
     {self.params['group']}  group, creates the file
     {self.params['marker']}  and relies ENTIRELY on the group_vars
     setting for escalation (no become_user: in the playbook itself).

The file must end up owned by {self.params['become_user']}, not root.
"""
        self.hints = [
            "group_vars/<group>.yml: ansible_become: true, "
            "ansible_become_user: " + self.params["become_user"] + ", "
            "ansible_become_method: sudo",
            "This needs the target user to exist and have sudo rights on "
            "the managed node already — the point graded here is the "
            "GROUP-SCOPED CONFIGURATION, not provisioning that account.",
        ]
        self.exam_tips = [
            "become_user in ansible.cfg or on a task is GLOBAL/per-task; "
            "group_vars scopes it to exactly the hosts that need it — "
            "useful when different tiers escalate to different service "
            "accounts.",
        ]
        return self

    def validate(self):
        res = self.result()
        group, user = self.params["group"], self.params["become_user"]
        if not self.check_exists(res, f"group_vars/{group}.yml"):
            return res
        self.check_contains(res, f"group_vars/{group}.yml",
                            r"ansible_become:\s*(true|yes)",
                            "group_vars enables become for the group")
        self.check_contains(res, f"group_vars/{group}.yml",
                            rf"ansible_become_user:\s*{user}",
                            f"group_vars escalates to {user}")
        self.check_contains(res, "become_config.yml", rf"hosts:\s*{group}\b",
                            "playbook targets the restricted group")
        if not self.check_playbook_runs(res, "become_config.yml",
                                        require_idempotent=False):
            return res
        self.check_node_state(res, f"{self.params['marker']} is owned by {user}",
                              group, "ansible.builtin.command",
                              f"stat -c %U {self.params['marker']}",
                              expect=user, become=True)
        return res


@TaskRegistry.register("managed_nodes")
class DeployFilesToNodesTask(AnsibleTask):
    """The explicit 'deploy files to managed nodes' objective bullet,
    tested with a REAL local file (src:), not inline content: — most
    other tasks in this catalog only ever use content:."""

    def __init__(self):
        super().__init__("mn_deploy_files_001", "managed_nodes", "easy")

    def generate(self, **params):
        self.params = {"local": "files/site_policy.txt",
                       "dest": "/etc/site_policy.txt",
                       "text": "Managed by the site automation team."}
        self.description = f"""
In your working directory ({self.workdir}):

  1. Create a REAL local file  {self.params['local']}  containing:
        {self.params['text']}
  2. Create a playbook  deploy_files.yml  that copies THAT LOCAL FILE
     (via  src: , reading an actual file from the control node — not
     content: with inline text) to  {self.params['dest']}  on ALL
     managed nodes, mode 0644.

Idempotent.
"""
        self.hints = [
            "copy: src: files/site_policy.txt  dest: " + self.params["dest"] +
            "  mode: '0644' — src: with a relative path is resolved "
            "against the playbook's own files/ directory automatically.",
            "content: embeds text directly in the playbook; src: pushes a "
            "real file that already exists on the control node — the "
            "exam distinguishes between the two.",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_exists(res, self.params["local"]):
            return res
        self.check_contains(res, "deploy_files.yml",
                            rf"src:\s*.*{self.params['local'].split('/')[-1]}",
                            "playbook copies the real local file via src:")
        if not self.check_playbook_runs(res, "deploy_files.yml"):
            return res
        self.check_node_state(res, f"{self.params['dest']} has the deployed content",
                              "all", "ansible.builtin.command",
                              f"cat {self.params['dest']}",
                              expect=re.escape(self.params["text"]), become=True)
        return res
