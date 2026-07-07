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
