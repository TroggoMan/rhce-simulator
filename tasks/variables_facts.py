"""Domain 3: variables, facts and registered results."""

import random

from core.registry import TaskRegistry
from tasks.base import AnsibleTask


@TaskRegistry.register("variables_facts")
class FactsReportTask(AnsibleTask):
    def __init__(self):
        super().__init__("vf_facts_report_001", "variables_facts", "medium")

    def generate(self, **params):
        dest = params.get("dest") or random.choice(
            ["/root/hwreport.txt", "/root/system_report.txt"])
        self.params = {"dest": dest}
        self.description = f"""
Create a playbook  facts_report.yml  in your working directory
({self.workdir}) that generates  {dest}  on ALL managed nodes containing
exactly these three lines, populated from Ansible facts:

    HOSTNAME=<short hostname>
    MEMORY=<total memory in MB>
    BIOS=<bios version>

If a value is unavailable on a node, the word NONE must appear instead.
The playbook must be idempotent.
"""
        self.hints = [
            "copy with content: and {{ ansible_facts['memtotal_mb'] }} etc.",
            "The | default('NONE') filter covers missing facts.",
            "Inspect available facts with: ansible <node> -m setup",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "facts_report.yml", r"ansible_facts|ansible_memtotal",
                            "playbook reads Ansible facts")
        if not self.check_playbook_runs(res, "facts_report.yml"):
            return res
        self.check_node_state(res, f"{self.params['dest']} has all three fields",
                              "all", "ansible.builtin.command",
                              f"cat {self.params['dest']}",
                              expect=r"HOSTNAME=\S+[\s\S]*MEMORY=\S+[\s\S]*BIOS=\S+",
                              become=True)
        return res


@TaskRegistry.register("variables_facts")
class RegisterOutputTask(AnsibleTask):
    def __init__(self):
        super().__init__("vf_register_001", "variables_facts", "easy")

    def generate(self, **params):
        cmd, outfile = params.get("pair") or random.choice([
            ("df -h /", "/root/disk_usage.txt"),
            ("uptime", "/root/uptime.txt"),
            ("ip -brief addr", "/root/net_addr.txt"),
        ])
        self.params = {"cmd": cmd, "outfile": outfile}
        self.description = f"""
Create a playbook  register.yml  in your working directory ({self.workdir})
that, on ALL managed nodes:

  1. runs the command   {cmd}
  2. captures its output in a variable using  register
  3. writes that captured stdout to the file  {outfile}

(The command task itself may report "changed"; only the file-writing part
needs to be idempotent.)
"""
        self.hints = [
            "register: result  then  {{ result.stdout }}",
            "copy with content: writes a variable to a file.",
            "Add changed_when: false to the command task to keep runs clean.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "register.yml", r"register:",
                            "playbook registers command output")
        if not self.check_playbook_runs(res, "register.yml",
                                        require_idempotent=False):
            return res
        self.check_node_state(res, f"{self.params['outfile']} is non-empty",
                              "all", "ansible.builtin.command",
                              f"grep -c . {self.params['outfile']}",
                              expect=r"^\s*\S+ \| (CHANGED|SUCCESS)[\s\S]*[1-9]",
                              become=True)
        return res


@TaskRegistry.register("variables_facts")
class CustomFactsTask(AnsibleTask):
    """Custom facts (facts.d) — extending what 'setup' reports with your
    own site-specific data, surfaced under ansible_facts.ansible_local."""

    def __init__(self):
        super().__init__("vf_custom_facts_001", "variables_facts", "hard")

    def generate(self, **params):
        role = params.get("role") or random.choice(["webtier", "dbtier", "cachetier"])
        self.params = {"role": role, "outfile": "/root/role_report.txt"}
        self.description = f"""
Create a playbook  custom_facts.yml  in your working directory
({self.workdir}) that, on ALL managed nodes:

  1. deploys an executable custom fact script to
     /etc/ansible/facts.d/sitefacts.fact  that prints JSON like:
        {{"role": "{role}"}}
  2. RE-GATHERS facts (custom facts are only picked up by a fresh gather,
     not the one already cached from the start of the play)
  3. writes  {self.params['outfile']}  containing the value read back from
     the custom fact — NOT a hard-coded string — via
     ansible_facts['ansible_local']['sitefacts']['role']

Idempotent (steps 1 and 3; re-gathering facts is inherently non-destructive).
"""
        self.hints = [
            "/etc/ansible/facts.d/*.fact must be executable and print valid "
            "JSON (or INI) to stdout — Ansible runs it and merges the output "
            "under ansible_local.",
            "ansible.builtin.setup (or gather_facts again via meta: "
            "clear_facts + a following task) refreshes ansible_local after "
            "the script is deployed.",
            "Deploying the script with mode 0755 is required — a "
            "non-executable .fact file is silently ignored.",
        ]
        self.exam_tips = [
            "The classic trap: deploying the fact script and reading "
            "ansible_local in the SAME gather. Facts are gathered once at "
            "play start, before your deploy task has even run — you must "
            "re-gather afterward.",
        ]
        return self

    def validate(self):
        res = self.result()
        role = self.params["role"]
        self.check_contains(res, "custom_facts.yml", r"facts\.d",
                            "playbook deploys into /etc/ansible/facts.d")
        self.check_contains(res, "custom_facts.yml", r"ansible_local",
                            "playbook reads back ansible_local")
        if not self.check_playbook_runs(res, "custom_facts.yml"):
            return res
        self.check_node_state(res, "custom fact script is executable", "all",
                              "ansible.builtin.command",
                              "test -x /etc/ansible/facts.d/sitefacts.fact",
                              become=True)
        self.check_node_state(res, f"{self.params['outfile']} reflects the custom fact",
                              "all", "ansible.builtin.command",
                              f"cat {self.params['outfile']}", expect=role,
                              become=True)
        return res


@TaskRegistry.register("variables_facts")
class GroupVarsHostVarsTask(AnsibleTask):
    """Variable precedence: host_vars beats group_vars for the same
    variable name — a concrete demonstration, not just a rule to memorize."""

    def __init__(self):
        super().__init__("vf_precedence_001", "variables_facts", "medium")

    def generate(self, **params):
        nodes = self.nodes
        override_host = nodes[0]
        self.params = {"override_host": override_host,
                       "group_value": "standard", "host_value": "priority",
                       "outfile": "/root/tier.txt"}
        self.description = f"""
Demonstrate Ansible's variable precedence using files, not inline vars:.
In your working directory ({self.workdir}):

  1. Create  group_vars/all.yml  defining:  service_tier: {self.params['group_value']}
  2. Create  host_vars/{override_host}.yml  defining:
        service_tier: {self.params['host_value']}
  3. Create a playbook  precedence.yml  that writes  {self.params['outfile']}
     on ALL managed nodes with the content:  TIER=<service_tier>

Every node EXCEPT {override_host} must end up with
TIER={self.params['group_value']} ; {override_host} must end up with
TIER={self.params['host_value']}  — proving host_vars overrides group_vars
for the exact same variable name.

Idempotent.
"""
        self.hints = [
            "group_vars/ and host_vars/ are auto-loaded by filename match "
            "(all.yml, <hostname>.yml) — no vars_files: needed in the "
            "playbook at all.",
            "host_vars sits ABOVE group_vars in Ansible's precedence order "
            "regardless of which one was 'created last'.",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_exists(res, "group_vars/all.yml"):
            return res
        if not self.check_exists(res, f"host_vars/{self.params['override_host']}.yml"):
            return res
        self.check_contains(res, "group_vars/all.yml",
                            rf"service_tier:\s*{self.params['group_value']}",
                            "group_vars sets the baseline service_tier")
        self.check_contains(res, f"host_vars/{self.params['override_host']}.yml",
                            rf"service_tier:\s*{self.params['host_value']}",
                            "host_vars overrides service_tier for one host")
        if not self.check_playbook_runs(res, "precedence.yml"):
            return res
        self.check_node_state(res, f"{self.params['override_host']} shows the host_vars value",
                              self.params["override_host"], "ansible.builtin.command",
                              f"cat {self.params['outfile']}",
                              expect=rf"TIER={self.params['host_value']}", become=True)
        return res
