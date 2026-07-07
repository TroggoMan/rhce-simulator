"""
Domain 2: automation content navigator. Navigator + execution environments
are the headline additions in the RHEL 10 version of EX294. These tasks
degrade gracefully when ansible-navigator isn't installed (static checks
still grade the artifacts).
"""

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
