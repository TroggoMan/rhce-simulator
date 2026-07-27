"""
Domain 2: automation content navigator. Navigator + execution environments
are the headline additions in the RHEL 10 version of EX294. These tasks
degrade gracefully when ansible-navigator isn't installed (static checks
still grade the artifacts).
"""

import random

from core.registry import TaskRegistry
from tasks.base import AnsibleTask
from validators import ansible_runner as runner


@TaskRegistry.register("navigator")
class NavigatorRunTask(AnsibleTask):
    def __init__(self):
        super().__init__("nav_run_001", "navigator", "medium")

    def generate(self, **params):
        self.params = {"playbook": "ping_all.yml", "outfile": "navigator_run.txt"}
        self.description = f"""
Using automation content navigator:

  1. Create a playbook  ping_all.yml  in your working directory
     ({self.workdir}) with a single play that runs the  ping  module
     against ALL managed nodes.
  2. Run it with  ansible-navigator  in stdout mode and save the complete
     output to  navigator_run.txt  in the same directory, e.g.:

       ansible-navigator run ping_all.yml --mode stdout | tee navigator_run.txt

The saved output must show the PLAY RECAP with zero failures.

(If ansible-navigator is not installed on this control node, install it
with:  pip install ansible-navigator  — or dnf on RHEL with AAP repos.)
"""
        self.hints = [
            "ansible-navigator run <playbook> --mode stdout",
            "Your ansible-navigator.yml from the config task can set mode: stdout permanently.",
            "Navigator uses execution environments by default; --ee false runs without podman.",
        ]
        return self

    def validate(self):
        res = self.result()
        ran = self.check_playbook_runs(res, self.params["playbook"])
        if not self.check_exists(res, self.params["outfile"]):
            return res
        self.check_contains(res, self.params["outfile"], r"PLAY RECAP",
                            "navigator_run.txt contains a play recap")
        self.check_contains(res, self.params["outfile"],
                            r"failed=0", "recorded run has no failures")
        if ran and runner.have_navigator():
            res.add("ansible-navigator available on control node", True)
        else:
            res.add("ansible-navigator available on control node",
                    runner.have_navigator(),
                    "install ansible-navigator to fully match the exam environment")
        return res


@TaskRegistry.register("navigator")
class NavigatorDocTask(AnsibleTask):
    """Domain 5: 'use ansible-navigator to FIND new modules in available
    Content Collections and use them' — the lookup half of navigator, which
    is what actually saves you on exam day when you can't recall an option
    name."""

    def __init__(self):
        super().__init__("nav_doc_001", "navigator", "medium")

    def generate(self, **params):
        module, keyword = params.get("pair") or random.choice([
            ("ansible.posix.firewalld", "firewall"),
            ("community.general.seport", "selinux"),
            ("ansible.posix.mount", "mount"),
        ])
        self.params = {
            "module": module,
            "keyword": keyword,
            "docfile": "module_doc.txt",
            "collfile": "collections.txt",
        }
        self.description = f"""
The exam gives you no internet — the documentation on the machine is all
you get. Practice pulling it up.

In your working directory ({self.workdir}), using  ansible-navigator  in
stdout mode:

  1. Save the full module documentation for

         {module}

     to a file named  {self.params['docfile']} .

  2. Save the list of Ansible Content Collections available on this control
     node to a file named  {self.params['collfile']} .

Both files must contain real captured output, and {self.params['docfile']}
must include the module's OPTIONS section — that's the part you actually
need mid-exam.
"""
        self.hints = [
            "ansible-navigator doc {} --mode stdout > {}".format(
                module, self.params["docfile"]),
            "ansible-navigator collections --mode stdout > {}".format(
                self.params["collfile"]),
            "Add --ee false if you don't have podman / an execution "
            "environment image pulled — navigator defaults to running "
            "inside one.",
            "ansible-doc {} works too and is the fallback worth "
            "memorising.".format(module),
        ]
        self.exam_tips = [
            "Knowing a module exists is worth nothing if you can't recall "
            "its option names. 'navigator doc <module>' (or ansible-doc) is "
            "the single highest-value keystroke sequence on the exam.",
            "ansible-navigator collections tells you what content is "
            "actually installed — use it before assuming a module is "
            "available.",
        ]
        return self

    def validate(self):
        res = self.result()
        p = self.params
        short = p["module"].split(".")[-1]
        if not self.check_exists(res, p["docfile"]):
            return res
        self.check_contains(res, p["docfile"], short,
                            f"{p['docfile']} documents {p['module']}")
        self.check_contains(res, p["docfile"], r"OPTIONS|options:",
                            "captured docs include the OPTIONS section")
        if not self.check_exists(res, p["collfile"]):
            return res
        self.check_contains(res, p["collfile"], r"ansible\.builtin|ansible\.posix|community",
                            "collection listing contains real collections")
        res.add("ansible-navigator available on control node",
                runner.have_navigator(),
                "" if runner.have_navigator() else
                "install ansible-navigator to match the exam environment")
        return res
