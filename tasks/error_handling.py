"""Domain 3: handlers, blocks, rescue and always."""

import random

from core.registry import TaskRegistry
from tasks.base import AnsibleTask


@TaskRegistry.register("error_handling")
class HandlerTask(AnsibleTask):
    def __init__(self):
        super().__init__("eh_handler_001", "error_handling", "medium")

    def generate(self, **params):
        text = params.get("text") or random.choice(
            ["Welcome to the automated web farm", "Deployed by Ansible",
             "RHCE practice site"])
        self.params = {"text": text}
        self.description = f"""
Create a playbook  handler.yml  in your working directory ({self.workdir})
for ALL managed nodes that:

  * ensures httpd is installed and running
  * deploys  /var/www/html/index.html  with the content:
        {text}
  * restarts httpd via a HANDLER — but only when the index.html content
    actually changes (that is what handlers are for)

Idempotent: the second run must not restart httpd.
"""
        self.hints = [
            "notify: on the copy task, matching name under handlers:.",
            "Handlers run once at the end of the play, only if notified.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "handler.yml", r"notify:", "task notifies a handler")
        self.check_contains(res, "handler.yml", r"handlers:", "play defines handlers")
        if not self.check_playbook_runs(res, "handler.yml"):
            return res
        self.check_node_state(res, "index.html deployed with required content",
                              "all", "ansible.builtin.command",
                              "cat /var/www/html/index.html",
                              expect=self.params["text"], become=True)
        self.check_node_state(res, "httpd is active", "all",
                              "ansible.builtin.command",
                              "systemctl is-active httpd", expect=r"\bactive\b",
                              become=True)
        return res


@TaskRegistry.register("error_handling")
class BlockRescueTask(AnsibleTask):
    def __init__(self):
        super().__init__("eh_block_rescue_001", "error_handling", "hard")

    def generate(self, **params):
        self.params = {
            "attempt": "/var/tmp/primary_step",
            "rescue_marker": "/var/tmp/rescue_ran",
            "always_marker": "/var/tmp/always_ran",
        }
        self.description = f"""
Create a playbook  block_rescue.yml  in your working directory
({self.workdir}) for ALL managed nodes demonstrating error handling:

  * a  block  section runs a task that is GUARANTEED to fail
    (for example the command  /bin/false )
  * the  rescue  section creates the file  {self.params['rescue_marker']}
  * the  always  section creates the file  {self.params['always_marker']}

The playbook as a whole must finish successfully (rc 0) on every node —
that is the point of rescue.
"""
        self.hints = [
            "block: / rescue: / always: are siblings under one task entry.",
            "A rescued failure does not fail the play.",
            "file module with state: touch (or copy with content:) for the markers.",
        ]
        return self

    def validate(self):
        res = self.result()
        for kw in ("block:", "rescue:", "always:"):
            self.check_contains(res, "block_rescue.yml", kw.replace(":", r":"),
                                f"playbook has a {kw} section")
        # touch/false are inherently non-idempotent; grade run success only.
        if not self.check_playbook_runs(res, "block_rescue.yml",
                                        require_idempotent=False):
            return res
        for marker in (self.params["rescue_marker"], self.params["always_marker"]):
            self.check_node_state(res, f"{marker} exists on all nodes",
                                  "all", "ansible.builtin.command",
                                  f"test -e {marker}", become=True)
        return res
