"""
Domain 2: ad-hoc commands. The classic exam form is "write a script that
uses an ad-hoc command", which grades both the script artifact and the
state it produces.
"""

import os
import random

from core.registry import TaskRegistry
from tasks.base import AnsibleTask
from validators import ansible_runner as runner


@TaskRegistry.register("adhoc")
class AdhocScriptTask(AnsibleTask):
    def __init__(self):
        super().__init__("adhoc_script_001", "adhoc", "easy")

    def generate(self, **params):
        marker = params.get("marker") or random.choice(
            ["/etc/motd.d/adhoc", "/var/tmp/adhoc_was_here", "/etc/adhoc.marker"])
        text = params.get("text") or random.choice(
            ["Managed by Ansible", "EX294 practice system", "Automation in effect"])
        self.params = {"marker": marker, "text": text}
        self.description = f"""
Create a shell script  {self.workdir}/adhoc.sh  that uses an Ansible
ad-hoc command, not a playbook, to create the file  {marker}  on ALL
managed nodes with exactly this content:

    {text}

The script must be executable and must run as  ./adhoc.sh ."""
        self.hints = [
            "ansible all -m ansible.builtin.copy -a 'content=\"...\" dest=...'",
            "copy's content= adds no trailing newline unless you include one.",
            "chmod +x adhoc.sh",
        ]
        return self

    def validate(self):
        res = self.result()
        script = self.workdir / "adhoc.sh"
        if not self.check_exists(res, "adhoc.sh"):
            return res
        res.add("adhoc.sh is executable", os.access(script, os.X_OK),
                "" if os.access(script, os.X_OK) else "chmod +x adhoc.sh")
        self.check_contains(res, "adhoc.sh", r"\bansible\b(?!-playbook).*-m\s",
                            "script uses an ad-hoc ansible command")
        if runner.have_ansible():
            out = runner.run(["bash", str(script)], cwd=self.workdir)
            res.add("adhoc.sh runs successfully", out.ok,
                    "" if out.ok else out.text.strip()[-300:])
            self.check_node_state(
                res, f"{self.params['marker']} has the required content on all nodes",
                "all", "ansible.builtin.command",
                f"cat {self.params['marker']}", expect=self.params["text"],
                become=True)
        return res


@TaskRegistry.register("adhoc")
class AdhocPackageFactsScriptTask(AnsibleTask):
    """Ad-hoc queries aren't limited to command/shell — package_facts is the
    module form of 'is this installed', and it's what the exam expects you
    to reach for instead of parsing rpm -q output."""

    def __init__(self):
        super().__init__("adhoc_pkgfacts_001", "adhoc", "medium")

    def generate(self, **params):
        pkg = params.get("pkg") or random.choice(["tar", "rsync", "vim-enhanced"])
        self.params = {"pkg": pkg, "outfile": "pkg_audit.txt"}
        self.description = f"""
Create a shell script  {self.workdir}/pkg_audit.sh  that uses a SINGLE
ad-hoc command with the  ansible.builtin.package_facts  module against ALL
managed nodes to report whether the package  {pkg}  is installed, writing
the raw output to  {self.workdir}/{self.params['outfile']} .

The script must be executable and must run as  ./pkg_audit.sh ."""
        self.hints = [
            "ansible all -m ansible.builtin.package_facts -a 'manager=auto'",
            "package_facts populates ansible_facts.packages — it doesn't print "
            "a yes/no by itself, so redirect or tee the raw ad-hoc output.",
        ]
        self.exam_tips = [
            "package_facts is the module form of 'is this installed'. Reach "
            "for it instead of parsing rpm -q output through command.",
        ]
        return self

    def validate(self):
        res = self.result()
        script = self.workdir / "pkg_audit.sh"
        if not self.check_exists(res, "pkg_audit.sh"):
            return res
        res.add("pkg_audit.sh is executable", os.access(script, os.X_OK),
                "" if os.access(script, os.X_OK) else "chmod +x pkg_audit.sh")
        self.check_contains(res, "pkg_audit.sh", r"package_facts",
                            "script uses the package_facts module")
        if runner.have_ansible():
            out = runner.run(["bash", str(script)], cwd=self.workdir)
            res.add("pkg_audit.sh runs successfully", out.ok,
                    "" if out.ok else out.text.strip()[-300:])
            if self.check_exists(res, self.params["outfile"]):
                # Grade the captured output, not just its existence: a real
                # package_facts run reports the fact key and one result
                # header per targeted host. Deliberately NOT keyed on the
                # package being present — the task is to report whether it
                # is installed, and "absent" is a valid finding.
                self.check_contains(res, self.params["outfile"],
                                    r"packages",
                                    "captured output holds package facts")
                for node in self.nodes:
                    self.check_contains(
                        res, self.params["outfile"],
                        rf"{node}\s*\|\s*(SUCCESS|CHANGED)",
                        f"output records a result for {node}")
        return res


@TaskRegistry.register("adhoc")
class AdhocHostPatternTask(AnsibleTask):
    """Host-pattern fluency: limit expressions, group math, and exclusion —
    the ad-hoc skill that makes 'run this everywhere EXCEPT...' possible."""

    def __init__(self):
        super().__init__("adhoc_pattern_001", "adhoc", "medium")

    def generate(self, **params):
        marker = params.get("marker") or "/var/tmp/prod_only.marker"
        self.params = {"marker": marker}
        self.description = f"""
Create a shell script  {self.workdir}/pattern.sh  that uses a SINGLE
ad-hoc command targeting a host pattern — every host in the  prod  group
that is not also in the  dev  group — to create the file  {marker}  with
the content  prod-only .

The script must be executable and must run as  ./pattern.sh ."""
        self.hints = [
            "Host pattern syntax: 'prod:!dev' excludes dev from prod.",
            "ansible 'prod:!dev' -m ansible.builtin.copy -a 'content=... dest=...'",
            "Quote the pattern — the shell would otherwise try to expand '!' itself.",
        ]
        self.exam_tips = [
            "Group math is how you answer 'everywhere except...' without "
            "maintaining a second inventory group: ':' unions, ':&' "
            "intersects, ':!' excludes.",
        ]
        return self

    def validate(self):
        res = self.result()
        script = self.workdir / "pattern.sh"
        if not self.check_exists(res, "pattern.sh"):
            return res
        res.add("pattern.sh is executable", os.access(script, os.X_OK),
                "" if os.access(script, os.X_OK) else "chmod +x pattern.sh")
        self.check_contains(res, "pattern.sh", r"prod:!dev|prod\s*:\s*!\s*dev",
                            "script uses the prod:!dev host pattern")
        if runner.have_ansible():
            out = runner.run(["bash", str(script)], cwd=self.workdir)
            res.add("pattern.sh runs successfully", out.ok,
                    "" if out.ok else out.text.strip()[-300:])
            # Whether the pattern actually SELECTS anything depends on the
            # inventory the candidate built, so ask before grading it. If
            # prod:!dev resolves to nobody the file legitimately cannot
            # land anywhere and the artifact check above is all there is.
            landed = f"{self.params['marker']} landed on prod-only hosts"
            if self.probe("ansible.builtin.command", "true",
                          pattern="prod:!dev", require_all=False):
                self.check_node_state(res, landed, "prod:!dev",
                                      "ansible.builtin.command",
                                      f"cat {self.params['marker']}",
                                      expect="prod-only", become=True)
            else:
                res.add_skip(landed,
                             "no host in this inventory is in prod without "
                             "also being in dev, so the pattern selects "
                             "nothing to check")
        return res
