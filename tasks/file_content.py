"""Domain 4/7: file content management and archiving."""

import random
import re

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


@TaskRegistry.register("file_content")
class LineinfileConfigTask(AnsibleTask):
    """lineinfile against a REAL existing config file — ensure/modify one
    line without touching the rest, plus a mandatory backup."""

    def __init__(self):
        super().__init__("fcnt_lineinfile_001", "file_content", "medium")

    def generate(self, **params):
        setting = params.get("setting") or random.choice(
            [("MaxAuthTries", "3"), ("ClientAliveInterval", "300")])
        key, value = setting
        self.params = {"key": key, "value": value, "path": "/etc/ssh/sshd_config"}
        self.description = f"""
Create a playbook  lineinfile.yml  in your working directory
({self.workdir}) that, on ALL managed nodes, ensures the line

    {key} {value}

is present in  {self.params['path']}  — replacing any existing
(possibly commented-out) line that sets  {key} , not appending a
duplicate. A backup of the original file must be kept before the change.

The playbook must NOT restart sshd (a config-only change is being graded
here); it must be idempotent.
"""
        self.hints = [
            "ansible.builtin.lineinfile with regexp: '^#?" + key + r"\s' "
            "and line: '" + f"{key} {value}" + "'.",
            "backup: true keeps a timestamped copy before any change.",
            "A regexp that's too loose matches unrelated lines; too strict "
            "and it appends instead of replacing.",
        ]
        return self

    def validate(self):
        res = self.result()
        key, value = self.params["key"], self.params["value"]
        self.check_contains(res, "lineinfile.yml",
                            r"lineinfile\s*:|ansible\.builtin\.lineinfile",
                            "playbook uses the lineinfile module")
        self.check_contains(res, "lineinfile.yml", r"backup:\s*(true|yes)",
                            "change is backed up")
        self.check_contains(res, "lineinfile.yml", rf"regexp:.*{key}",
                            f"regexp targets the existing {key} line")
        if not self.check_playbook_runs(res, "lineinfile.yml"):
            return res
        self.check_node_state(res, f"{self.params['path']} has {key} {value}",
                              "all", "ansible.builtin.shell",
                              f"grep -E '^{key}\\s' {self.params['path']}",
                              expect=rf"{key}\s+{value}", become=True)
        self.check_node_state(res, f"only one {key} line remains", "all",
                              "ansible.builtin.shell",
                              f"grep -cE '^{key}\\s' {self.params['path']}",
                              expect=r"^1$", become=True)
        return res


@TaskRegistry.register("file_content")
class UnarchiveTask(AnsibleTask):
    """The inverse of ArchiveTask: unpack a tarball ONTO managed nodes,
    with the from-the-control-node vs. already-remote distinction that
    trips people up (remote_src)."""

    def __init__(self):
        super().__init__("fcnt_unarchive_001", "file_content", "medium")

    def generate(self, **params):
        dest = params.get("dest") or random.choice(
            ["/opt/payload", "/srv/content"])
        self.params = {"dest": dest, "archive": "payload.tar.gz",
                       "marker_name": "PAYLOAD_MARKER.txt"}
        self.description = f"""
In your working directory ({self.workdir}):

  1. Create a local tar.gz archive named  {self.params['archive']}
     containing a single file  {self.params['marker_name']}  with any
     content (build it however you like — tar, or an Ansible ad-hoc
     archive task; this part isn't graded).
  2. Create a playbook  unarchive.yml  that, on ALL managed nodes,
     extracts that archive FROM THE CONTROL NODE into  {dest}  (creating
     the directory if needed), using the  ansible.builtin.unarchive
     module — not shell/command, not the archive module (that COMPRESSES,
     this task DECOMPRESSES).

After running,  {dest}/{self.params['marker_name']}  must exist on every
managed node.
"""
        self.hints = [
            "unarchive: src: " + self.params["archive"] + "  dest: " + dest,
            "Do NOT set remote_src: true — the archive lives on the "
            "CONTROL node and must be copied over before extraction, which "
            "is the module's default behaviour.",
            "remote_src: true is for when the archive is ALREADY on the "
            "managed node (e.g. downloaded there) — using it here means "
            "the module looks for the file on the wrong host.",
        ]
        self.exam_tips = [
            "unarchive vs. archive is a naming trap: archive CREATES a "
            "compressed file, unarchive EXTRACTS one. Reading only the "
            "module name (not which direction it goes) is a common mistake.",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_exists(res, self.params["archive"]):
            return res
        self.check_contains(res, "unarchive.yml",
                            r"unarchive\s*:|ansible\.builtin\.unarchive",
                            "playbook uses the unarchive module")
        try:
            text = (self.workdir / "unarchive.yml").read_text(
                encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        not_remote_src = re.search(r"remote_src:\s*(true|yes)", text,
                                   re.IGNORECASE) is None
        res.add("archive is pushed from the control node (remote_src not true)",
                not_remote_src, "" if not_remote_src else
                "remove remote_src: true — the archive lives on the control node")
        if not self.check_playbook_runs(res, "unarchive.yml"):
            return res
        target = f"{self.params['dest']}/{self.params['marker_name']}"
        self.check_node_state(res, f"{target} exists on all nodes",
                              "all", "ansible.builtin.command",
                              f"test -e {target}", become=True)
        return res
