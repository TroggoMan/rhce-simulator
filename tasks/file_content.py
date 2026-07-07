"""Domain 4/7: file content management and archiving."""

import random

from core.registry import TaskRegistry
from tasks.base import AnsibleTask


@TaskRegistry.register("file_content")
class IssueFileTask(AnsibleTask):
    def __init__(self):
        super().__init__("fcnt_issue_001", "file_content", "easy")

    def generate(self, **params):
        mapping = params.get("mapping") or {
            "dev": "Development",
            "prod": "Production",
        }
        self.params = {"mapping": mapping}
        rules = "\n".join(f"      hosts in group {g}:  {t}"
                          for g, t in mapping.items())
        self.description = f"""
Create a playbook  issue.yml  in your working directory ({self.workdir})
that sets the content of  /etc/issue  depending on group membership
(your inventory's dev/prod groups):

{rules}

Exactly one line, idempotent.
"""
        self.hints = [
            "copy with content: plus when: \"'dev' in group_names\" — or one task "
            "using a variable set per group (group_vars work too).",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_playbook_runs(res, "issue.yml"):
            return res
        for group, text in self.params["mapping"].items():
            self.check_node_state(res, f"/etc/issue on {group} hosts says {text}",
                                  group, "ansible.builtin.command",
                                  "cat /etc/issue", expect=text, become=True)
        return res


@TaskRegistry.register("file_content")
class ArchiveTask(AnsibleTask):
    def __init__(self):
        super().__init__("fcnt_archive_001", "file_content", "medium")

    def generate(self, **params):
        src, dest = params.get("pair") or random.choice([
            ("/etc/ssh", "/root/ssh_backup.tar.gz"),
            ("/var/log", "/root/log_backup.tar.gz"),
            ("/etc/sysconfig", "/root/sysconfig_backup.tar.gz"),
        ])
        self.params = {"src": src, "dest": dest}
        self.description = f"""
Create a playbook  archive.yml  in your working directory ({self.workdir})
that, on ALL managed nodes, creates a gzip-compressed tar archive
{dest}  containing the contents of  {src} .

Use the  community.general.archive  module (install the collection if it
is missing — that is part of the exam skill).
"""
        self.hints = [
            "ansible-galaxy collection install community.general",
            "archive: path: …, dest: …, format: gz",
            "The archive module is idempotent when the source hasn't changed.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "archive.yml", r"archive\s*:",
                            "playbook uses the archive module")
        # /var/log changes constantly, so don't demand changed=0 on rerun.
        if not self.check_playbook_runs(res, "archive.yml",
                                        require_idempotent=False):
            return res
        self.check_node_state(res, f"{self.params['dest']} is a valid gzip tar",
                              "all", "ansible.builtin.command",
                              f"tar tzf {self.params['dest']}", become=True)
        return res
