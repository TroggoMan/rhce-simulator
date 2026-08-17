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


def _note_navigator(res):
    """Record whether navigator is installed WITHOUT scoring the candidate.

    Whether ansible-navigator exists on the control node is a property of
    the lab, not of the candidate's work — every task here is still
    solvable with ansible-doc/ansible-playbook on a node that lacks it.
    Failing the check would penalise a correct answer for the lab's gap,
    so it's a skip: reported with the reason, excluded from the score.
    """
    if runner.have_navigator():
        return res.add("ansible-navigator available on control node", True)
    return res.add_skip(
        "ansible-navigator available on control node",
        "not installed on this control node — install it to match the "
        "exam environment")


@TaskRegistry.register("navigator")
class NavigatorRunTask(AnsibleTask):
    def __init__(self):
        super().__init__("nav_run_001", "navigator", "medium")

    def generate(self, **params):
        self.params = {"playbook": "ping_all.yml", "outfile": "navigator_run.txt"}
        self.description = f"""
Using automation content navigator:

  1. Create a playbook  {self.workdir}/{self.params['playbook']}  with a
     single play that runs the  ping  module against ALL managed nodes.
  2. Run it with  ansible-navigator  in stdout mode, saving the complete
     output to  {self.workdir}/{self.params['outfile']} .

The saved output must show the play recap with zero failures."""
        self.hints = [
            "ansible-navigator run <playbook> --mode stdout | tee <outfile>",
            "Your ansible-navigator.yml from the config task can set mode: stdout permanently.",
            "Navigator uses execution environments by default; --ee false runs without podman.",
            "Not installed? pip install ansible-navigator, or dnf on RHEL "
            "with the AAP repos enabled.",
        ]
        self.exam_tips = [
            "Without --mode stdout navigator opens its TUI, which is fine "
            "interactively and useless when you need output in a file.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_playbook_runs(res, self.params["playbook"])
        if not self.check_exists(res, self.params["outfile"]):
            return res
        self.check_contains(res, self.params["outfile"], r"PLAY RECAP",
                            "navigator_run.txt contains a play recap")
        self.check_contains(res, self.params["outfile"],
                            r"failed=0", "recorded run has no failures")
        _note_navigator(res)
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
        # The option names are what the check actually looks for: they're
        # specific enough to that module that the file can only contain
        # them if the candidate really pulled the docs up, which is the
        # habit this task exists to build.
        module, keyword, options = params.get("pair") or random.choice([
            ("ansible.posix.firewalld", "firewall", ["zone", "permanent"]),
            ("community.general.seport", "selinux", ["setype", "proto"]),
            ("ansible.posix.mount", "mount", ["fstype", "boot"]),
        ])
        self.params = {
            "module": module,
            "keyword": keyword,
            "options": options,
            "docfile": "module_doc.txt",
            "collfile": "collections.txt",
        }
        self.description = f"""
Using  ansible-navigator  in stdout mode:

  1. Save the full module documentation for

         {module}

     to  {self.workdir}/{self.params['docfile']} , including the module's
     OPTIONS section.

  2. Save the list of Ansible Content Collections available on this
     control node to  {self.workdir}/{self.params['collfile']} .
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
            "The exam gives you no internet — the documentation on the "
            "machine is all you get, so knowing a module exists is worth "
            "nothing if you can't recall its option names. "
            "'navigator doc <module>', or ansible-doc, is the single "
            "highest-value keystroke sequence on the exam.",
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
        for opt in p["options"]:
            self.check_contains(res, p["docfile"], rf"\b{opt}\b",
                                f"docs list the '{opt}' option of {p['module']}")
        if not self.check_exists(res, p["collfile"]):
            return res
        self.check_contains(res, p["collfile"], r"ansible\.builtin|ansible\.posix|community",
                            "collection listing contains real collections")
        _note_navigator(res)
        return res


@TaskRegistry.register("navigator")
class NavigatorInventoryTask(AnsibleTask):
    """navigator's OWN inventory subcommand — different from
    ansible-inventory, and part of the domain-5 'use navigator to
    configure the Ansible environment' bullet specifically."""

    def __init__(self):
        super().__init__("nav_inventory_001", "navigator", "medium")

    def generate(self, **params):
        self.params = {"outfile": "navigator_inventory.txt"}
        self.description = f"""
Using automation content navigator rather than the  ansible-inventory
command, dump the inventory your  ansible.cfg  points at to
{self.workdir}/{self.params['outfile']} .

The output must list every host currently in that inventory."""
        self.hints = [
            "ansible-navigator inventory --mode stdout -i inventory > "
            + self.params["outfile"],
            "Without --mode stdout this opens the TUI browser instead of "
            "printing to your terminal/file.",
            "-i (or your ansible.cfg's inventory= setting) tells navigator "
            "which inventory to load — it doesn't discover one on its own "
            "the way ansible-playbook does from ansible.cfg alone in every "
            "navigator version.",
        ]
        self.exam_tips = [
            "navigator's inventory subcommand is the one that answers "
            "'did my groups come out the way I think' before you waste a "
            "play run finding out they didn't.",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_exists(res, self.params["outfile"]):
            return res
        for node in self.nodes:
            self.check_contains(res, self.params["outfile"], node,
                                f"inventory output mentions {node}")
        _note_navigator(res)
        return res


@TaskRegistry.register("navigator")
class NavigatorNoEETask(AnsibleTask):
    """Execution-environment awareness, graded on what it actually changes.

    Navigator runs plays inside an EE container by default, so the
    collections available are the image's, not the control node's — the
    real-world symptom is a module that's installed but "not found".
    Turning the EE off in ansible-navigator.yml is the fix, and unlike
    reciting it, it leaves a checkable config file AND a play that has to
    survive a real run against the nodes.

    Config keys here are deliberately disjoint from cfg_navigator_001,
    which owns mode/artifacts/pull-policy.
    """

    def __init__(self):
        super().__init__("nav_no_ee_001", "navigator", "medium")

    def generate(self, **params):
        marker = params.get("marker") or "ee-{}".format(random.randint(1000, 9999))
        self.params = {
            "marker": marker,
            "playbook": "no_ee.yml",
            "dest": "/etc/rhce-navigator.conf",
        }
        self.description = f"""
Plays must run against this control node's own Python and collections
rather than inside an execution environment container.

  1. In  {self.workdir}/ansible-navigator.yml , disable the execution
     environment.
  2. Create a playbook  {self.workdir}/{self.params['playbook']}  that
     creates  {self.params['dest']}  on ALL managed nodes containing the
     single line:

         {marker}

The playbook must be idempotent."""
        self.hints = [
            "execution-environment:  enabled: false   (nested under the "
            "top-level ansible-navigator: key)",
            "The same thing on the command line is --ee false, which is "
            "worth knowing for the exam when you can't edit the config.",
            "ansible.builtin.copy with content: is idempotent here; a "
            "shell echo redirect is not.",
        ]
        self.exam_tips = [
            "Navigator runs plays inside an EE container by default, so the "
            "collections a play can reach are the image's, not the control "
            "node's. That mismatch is why a module you just installed can "
            "still come back 'not found'.",
            "If a module 'isn't found' under navigator but ansible-doc on "
            "the control node finds it fine, you are looking at an "
            "execution environment, not a broken install.",
        ]
        return self

    def validate(self):
        res = self.result()
        p = self.params
        if not self.check_exists(res, "ansible-navigator.yml"):
            return res
        self.check_contains(
            res, "ansible-navigator.yml",
            r"execution-environment:[\s\S]{0,120}enabled:\s*(false|no)",
            "execution environment disabled in ansible-navigator.yml")
        if not self.check_playbook_runs(res, p["playbook"]):
            return res
        self.check_node_state(res, f"{p['dest']} contains {p['marker']}",
                              "all", "ansible.builtin.command",
                              f"cat {p['dest']}", expect=p["marker"],
                              become=True)
        _note_navigator(res)
        return res
