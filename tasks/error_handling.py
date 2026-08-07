"""
Domain 8: handlers, blocks, rescue/always, and the failure-semantics
keywords — failed_when, changed_when, ignore_errors, assert.

That second group is what the objective's "configure error handling" really
turns on: command/shell tasks report success purely from an exit code and
report "changed" every single time they run, so without these keywords a
playbook built on them can neither be idempotent nor correctly detect
failure.
"""

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
Create a playbook  {self.workdir}/handler.yml  for ALL managed nodes that:

  * ensures httpd is installed and running
  * deploys  /var/www/html/index.html  with the content:
        {text}
  * restarts httpd via a HANDLER, and only when the index.html content
    actually changes

The playbook must be idempotent: the second run must not restart httpd."""
        self.hints = [
            "notify: on the copy task, matching name under handlers:.",
            "Handlers run once at the end of the play, only if notified.",
        ]
        self.exam_tips = [
            "Restarting a service unconditionally is the difference between "
            "a playbook you can run hourly and one that bounces production "
            "every time it runs. That is what handlers are for.",
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
Create a playbook  {self.workdir}/block_rescue.yml  for ALL managed nodes
demonstrating error handling:

  * a  block  section runs a task that is GUARANTEED to fail
    (for example the command  /bin/false )
  * the  rescue  section creates the file  {self.params['rescue_marker']}
  * the  always  section creates the file  {self.params['always_marker']}

The playbook as a whole must finish successfully (rc 0) on every node —
that is the point of rescue."""
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


@TaskRegistry.register("error_handling")
class FailedWhenChangedWhenTask(AnsibleTask):
    """The keywords that make command/shell tasks behave like real modules."""

    def __init__(self):
        super().__init__("eh_failed_when_001", "error_handling", "hard")

    def generate(self, **params):
        marker = params.get("marker") or random.choice(
            ["/etc/rhce_audit.conf", "/etc/lab_policy.conf"])
        needle = params.get("needle") or "COMPLIANT"
        self.params = {"marker": marker, "needle": needle}
        self.description = f"""
Create a playbook  {self.workdir}/failure_semantics.yml  that audits ALL
managed nodes WITHOUT ever reporting a false failure or a false change:

  1. Run a command that greps  {marker}  for the word  {needle} .
     The file does NOT exist on these nodes, and grep exits non-zero when
     it finds nothing — neither of those is an error for an audit, so this
     task must NEVER be reported as failed, and must NEVER be reported as
     changed (it only reads).

  2. Register its result, then use  assert  to state the audit ran:
     the registered variable must have an  rc  defined.

  3. Print a debug message reporting whether the node is compliant, based
     on the registered result.

The whole playbook must report  failed=0  AND  changed=0  on EVERY run,
including the very first one."""
        self.hints = [
            "changed_when: false on a read-only command — otherwise it "
            "reports 'changed' every run and can never be idempotent.",
            "failed_when: false (or a real condition) stops a non-zero exit "
            "code being treated as failure. Prefer a precise condition over "
            "ignore_errors: true, which hides genuine errors too.",
            "assert: that: - result.rc is defined",
        ]
        self.exam_tips = [
            "ignore_errors: true is the blunt instrument — it suppresses "
            "every failure including the ones you wanted to know about. "
            "failed_when lets you say exactly which outcomes count as "
            "failure, which is what graders look for.",
            "A single command task without changed_when: false is enough to "
            "make an otherwise perfect playbook fail an idempotence check.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "failure_semantics.yml", r"changed_when:",
                            "read-only command marked with changed_when")
        self.check_contains(res, "failure_semantics.yml",
                            r"failed_when:|ignore_errors:",
                            "non-zero exit handled (failed_when/ignore_errors)")
        self.check_contains(res, "failure_semantics.yml", r"register:",
                            "command result is registered")
        self.check_contains(res, "failure_semantics.yml", r"assert:",
                            "playbook asserts the audit ran")
        # Idempotence IS the point of this task, so it is required here.
        self.check_playbook_runs(res, "failure_semantics.yml",
                                 require_idempotent=True)
        return res


@TaskRegistry.register("error_handling")
class RescueRetryAssertTask(AnsibleTask):
    """Recover from a failure by retrying differently, then prove it worked."""

    def __init__(self):
        super().__init__("eh_rescue_retry_001", "error_handling", "hard")

    def generate(self, **params):
        script = "/usr/local/bin/lab_deploy.sh"
        outfile = params.get("outfile") or "/var/tmp/deploy_state.txt"
        self.params = {"script": script, "outfile": outfile}
        self.description = f"""
A deploy script refuses to run unless it is given the right flag.

Create a playbook  {self.workdir}/deploy_retry.yml  that, on ALL managed
nodes:

  1. Deploys a script to  {script}  (mode 0755) with exactly this body:

        #!/bin/bash
        [ "$1" = "--force" ] || {{ echo "refusing without --force" >&2; exit 3; }}
        echo "deployed" > {outfile}

  2. In a  block , runs that script with NO arguments — which will fail.
  3. In the matching  rescue , runs it again WITH  --force , registers the
     result, and uses  assert  to confirm that retry exited 0. If the
     retry also failed, the play must fail with a clear message.
  4. In  always , prints a debug message summarising what happened.

The play must finish successfully on every node, and  {outfile}  must end
up containing  deployed ."""
        self.hints = [
            "block/rescue/always are keys of ONE task entry, not separate tasks.",
            "Deploy the script with copy: content: | and mode: '0755'.",
            "assert: that: - retry.rc == 0  with fail_msg: and success_msg:.",
            "A failure inside rescue is NOT itself rescued — that's what "
            "makes the assert meaningful.",
            "The script writes the same content every run, so the shell "
            "tasks here report changed every time. That is expected.",
        ]
        self.exam_tips = [
            "Registering a variable inside a block that failed leaves it "
            "defined but holding the failure — use | default() in the always "
            "section or your debug task will crash on an undefined variable.",
        ]
        return self

    def validate(self):
        res = self.result()
        for kw in ("block:", "rescue:", "always:"):
            self.check_contains(res, "deploy_retry.yml", kw,
                                f"playbook has a {kw} section")
        self.check_contains(res, "deploy_retry.yml", r"--force",
                            "rescue retries with --force")
        self.check_contains(res, "deploy_retry.yml", r"assert:",
                            "retry outcome is asserted")
        # The script rewrites its output file each run, so changed=0 is not
        # a fair expectation — the recovery path is what matters.
        if not self.check_playbook_runs(res, "deploy_retry.yml",
                                        require_idempotent=False):
            return res
        self.check_node_state(res, f"{self.params['script']} is executable",
                              "all", "ansible.builtin.command",
                              f"test -x {self.params['script']}", become=True)
        self.check_node_state(res, f"{self.params['outfile']} says 'deployed'",
                              "all", "ansible.builtin.command",
                              f"cat {self.params['outfile']}",
                              expect=r"deployed", become=True)
        return res


@TaskRegistry.register("error_handling")
class RetryUntilTask(AnsibleTask):
    """until/retries/delay — polling for a condition, a different failure
    pattern from block/rescue: here the SAME task just tries again."""

    def __init__(self):
        super().__init__("eh_retry_until_001", "error_handling", "medium")

    def generate(self, **params):
        counter_file = "/var/tmp/retry_counter"
        ready_file = params.get("ready_file") or "/var/tmp/service_ready"
        tries = params.get("tries") or random.choice([3, 4, 5])
        self.params = {"counter": counter_file, "ready": ready_file, "tries": tries}
        self.description = f"""
Simulate polling for a condition that isn't true yet. Create a playbook
{self.workdir}/poll_retry.yml  that, on ALL managed nodes:

  1. Runs a shell command that increments a counter file
     ({counter_file}) by 1 each time it's called, and creates
     {ready_file}  only once the counter reaches {tries}:

        bash -c 'c=$(cat {counter_file} 2>/dev/null || echo 0); c=$((c+1)); \\
        echo $c > {counter_file}; [ $c -ge {tries} ] && touch {ready_file}; \\
        [ -f {ready_file} ]'

  2. Uses  until  /  retries  /  delay  to keep running that command until
     it succeeds (i.e. {ready_file} exists), instead of failing on the
     first few attempts.

The playbook must finish successfully, and {ready_file} must exist
afterward on every node."""
        self.hints = [
            "register: result / until: result.rc == 0 / retries: <=N> / delay: 1",
            "retries counts ADDITIONAL attempts after the first — set it "
            "comfortably higher than the number of tries actually needed.",
            "changed_when: false keeps a polling command from reporting "
            "changed on every run once it settles.",
        ]
        self.exam_tips = [
            "until is for 'keep trying the SAME task until it succeeds'; "
            "block/rescue is for 'if this fails, do something DIFFERENT'. "
            "Mixing them up is a common source of lost points.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "poll_retry.yml", r"until:",
                            "playbook uses until: to poll")
        self.check_contains(res, "poll_retry.yml", r"retries:",
                            "playbook sets retries:")
        self.check_contains(res, "poll_retry.yml", r"delay:",
                            "playbook sets delay:")
        if not self.check_playbook_runs(res, "poll_retry.yml",
                                        require_idempotent=False):
            return res
        self.check_node_state(res, f"{self.params['ready']} exists on all nodes",
                              "all", "ansible.builtin.command",
                              f"test -e {self.params['ready']}", become=True)
        return res


@TaskRegistry.register("error_handling")
class BlockLevelWhenTask(AnsibleTask):
    """A when: on the block itself, not on each task inside it — one
    condition instead of repeating it on every task."""

    def __init__(self):
        super().__init__("eh_block_when_001", "error_handling", "medium")

    def generate(self, **params):
        marker = params.get("marker") or "/var/tmp/dev_only_block.marker"
        self.params = {"marker": marker, "group": "dev"}
        self.description = f"""
Create a playbook  {self.workdir}/block_when.yml  that runs against ALL
managed nodes and contains a single  block  with AT LEAST TWO tasks inside
it — for example, creating a directory and then creating the file
{marker}  inside it.

Put the condition on the BLOCK itself (a single  when:  key as a sibling
of  block: ), not repeated on each task inside it, so the block only runs
on hosts in the inventory group  {self.params['group']} .

Hosts NOT in {self.params['group']} must be left completely untouched by
this playbook, and the playbook must not fail on them."""
        self.hints = [
            "block: / when: are siblings — the condition is written ONCE, "
            "not copy-pasted onto every task inside the block.",
            "when: \"'dev' in group_names\" evaluates per-host.",
            "A block-level when: still lets each task inside register its "
            "own result independently.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "block_when.yml", r"block:",
                            "playbook has a block section")
        self.check_contains(res, "block_when.yml",
                            rf"when:[\s\S]{{0,60}}{self.params['group']}",
                            "condition is on the block, gating group membership")
        if not self.check_playbook_runs(res, "block_when.yml",
                                        require_idempotent=False):
            return res
        self.check_node_state(res, f"{self.params['marker']} exists on {self.params['group']} hosts",
                              self.params["group"], "ansible.builtin.command",
                              f"test -e {self.params['marker']}", become=True)
        return res
