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
Create a shell script  adhoc.sh  in your working directory ({self.workdir})
that uses an Ansible AD-HOC command (not a playbook) to create the file
{marker}  on ALL managed nodes with exactly this content:

    {text}

The script must be executable and runnable as  ./adhoc.sh .
"""
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
