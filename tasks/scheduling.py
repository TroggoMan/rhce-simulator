"""Domain 7: task scheduling automation."""

import random
import re

from core.registry import TaskRegistry
from tasks.base import AnsibleTask


@TaskRegistry.register("scheduling_auto")
class CronTask(AnsibleTask):
    def __init__(self):
        super().__init__("sched_cron_001", "scheduling_auto", "medium")

    def generate(self, **params):
        minutes = params.get("minutes") or random.choice([2, 5, 10])
        message = params.get("message") or "EX294 in progress"
        self.params = {"minutes": minutes, "message": message, "user": "natasha"}
        self.description = f"""
Create a playbook  cron.yml  in your working directory ({self.workdir})
that, on ALL managed nodes:

  * ensures the user  natasha  exists
  * configures a cron job FOR natasha (not root) that runs every
    {minutes} minutes and executes:

        logger "{message}"

Idempotent — re-running must not create duplicate cron entries.
"""
        self.hints = [
            "ansible.builtin.cron with user:, minute: '*/" + str(minutes) + "', job:.",
            "The cron module's name: field is what makes it idempotent.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "cron.yml", r"cron\s*:|ansible\.builtin\.cron",
                            "playbook uses the cron module")
        if not self.check_playbook_runs(res, "cron.yml"):
            return res
        self.check_node_state(
            res, "natasha's crontab has the logger job",
            "all", "ansible.builtin.command",
            f"crontab -l -u {self.params['user']}",
            expect=rf"\*/{self.params['minutes']}[\s\S]*logger", become=True)
        return res


@TaskRegistry.register("scheduling_auto")
class CronBackupTask(AnsibleTask):
    """Scheduling + archiving together — and the trap that you cannot call
    an Ansible module from inside a cron job."""

    def __init__(self):
        super().__init__("sched_backup_001", "scheduling_auto", "hard")

    def generate(self, **params):
        src = params.get("src") or random.choice(["/etc/ssh", "/etc/sysconfig"])
        hour = params.get("hour") or random.choice([1, 2, 3])
        self.params = {
            "src": src,
            "hour": hour,
            "backup_dir": "/backup",
            "archive": "/backup/config_backup.tar.gz",
            "user": "root",
        }
        p = self.params
        self.description = f"""
Create a playbook  cron_backup.yml  in your working directory
({self.workdir}) that sets up a scheduled backup on ALL managed nodes:

  1. ensure the directory  {p['backup_dir']}  exists, owned by root, mode 0755
  2. ensure the  tar  package is installed
  3. schedule a cron job, running as ROOT, every day at {p['hour']}:00,
     that archives  {p['src']}  into  {p['archive']}

     The job must be a real shell command — cron runs a shell, so an
     Ansible module cannot be used as the scheduled job itself.

  4. give the cron entry a name so re-running the playbook updates that one
     entry instead of appending a duplicate

Idempotent. Then prove it works: running the scheduled command by hand must
actually produce a valid gzip archive at {p['archive']}.
"""
        self.hints = [
            "ansible.builtin.cron with name:, user: root, minute: '0', "
            "hour: '{}', job:.".format(hour),
            "job: \"tar -czf {} {}\" — a plain command, because cron shells "
            "out. community.general.archive is an Ansible module and cannot "
            "run inside cron.".format(p["archive"], p["src"]),
            "The name: field is what makes the cron module idempotent — it "
            "becomes a comment marker in the crontab used to find the entry "
            "again.",
        ]
        self.exam_tips = [
            "People who have only practised the archive module reach for it "
            "here and produce a crontab line that can never run. Inside cron "
            "you are writing shell, not YAML.",
            "Scheduling the job is usually only half the marks — the grader "
            "runs the command to confirm it actually works.",
        ]
        return self

    def validate(self):
        res = self.result()
        p = self.params
        self.check_contains(res, "cron_backup.yml",
                            r"cron\s*:|ansible\.builtin\.cron",
                            "playbook uses the cron module")
        self.check_contains(res, "cron_backup.yml", r"name:",
                            "cron entry is named (idempotence marker)")
        self.check_contains(res, "cron_backup.yml", r"\btar\b",
                            "scheduled job is a real tar command")
        if not self.check_playbook_runs(res, "cron_backup.yml"):
            return res
        self.check_node_state(res, f"{p['backup_dir']} exists", "all",
                              "ansible.builtin.command",
                              f"test -d {p['backup_dir']}", become=True)
        self.check_node_state(res, "root's crontab has the daily backup job",
                              "all", "ansible.builtin.command",
                              "crontab -l -u root",
                              expect=rf"0\s+{p['hour']}\s[\s\S]*tar", become=True)
        # Prove the scheduled command actually works, rather than trusting
        # that a syntactically valid crontab line would have done something.
        self.check_node_state(res, "the scheduled command produces a real archive",
                              "all", "ansible.builtin.shell",
                              f"tar -czf {p['archive']} {p['src']} "
                              f"&& tar tzf {p['archive']} | head -1",
                              become=True)
        return res


@TaskRegistry.register("scheduling_auto")
class CronRemoveJobTask(AnsibleTask):
    """Decommissioning a stale cron entry — the opposite of every other
    scheduling task, and a real, commonly-graded exam skill on its own."""

    def __init__(self):
        super().__init__("sched_cron_remove_001", "scheduling_auto", "medium")

    def generate(self, **params):
        self.params = {"user": "natasha", "name": "Legacy report generator"}
        self.description = f"""
A cron job is being retired. Create a playbook  cron_remove.yml  in your
working directory ({self.workdir}) that, on ALL managed nodes:

  1. FIRST ensures the user  {self.params['user']}  exists, and schedules
     a cron job named  "{self.params['name']}"  for them (any schedule,
     any command — it just needs to exist so there's something to
     remove).
  2. THEN removes THAT SPECIFIC cron job by name, leaving the user
     account itself untouched.

Both steps live in the same playbook, in order. (Like any create-then-
remove-in-one-run playbook, this legitimately reports changed on every
run — the removal LOGIC is what's graded, not changed=0.)
"""
        self.hints = [
            "Two cron tasks: first state: present (or omitted — present "
            "is the default) with name: and job:, then a SECOND cron "
            "task with the SAME name: and state: absent.",
            "The cron module matches existing entries by their name: "
            "comment — get the name wrong on the removal task and it "
            "matches nothing.",
            "state: absent does NOT need job: — only name: is required "
            "to identify what to remove.",
        ]
        return self

    def validate(self):
        res = self.result()
        name = self.params["name"]
        self.check_contains(res, "cron_remove.yml", r"state:\s*absent",
                            "playbook removes a cron entry (state: absent)")
        self.check_contains(res, "cron_remove.yml", re.escape(name),
                            "removal task references the same job name")
        if not self.check_playbook_runs(res, "cron_remove.yml",
                                        require_idempotent=False):
            return res
        self.check_node_state(res, f"{self.params['user']}'s crontab no longer has the job",
                              "all", "ansible.builtin.shell",
                              f"crontab -l -u {self.params['user']} 2>/dev/null | "
                              f"grep -q '{name}' && echo STILL_THERE || echo REMOVED",
                              expect=r"REMOVED", become=True)
        return res


@TaskRegistry.register("scheduling_auto")
class AtOneTimeJobTask(AnsibleTask):
    """One-shot scheduling via 'at' — a genuinely different mechanism from
    cron's recurring model, and its own module (ansible.posix.at)."""

    def __init__(self):
        super().__init__("sched_at_001", "scheduling_auto", "medium")

    def generate(self, **params):
        minutes = params.get("minutes") or random.choice([5, 10, 15])
        marker = params.get("marker") or "/var/tmp/at_job_ran"
        self.params = {"minutes": minutes, "marker": marker}
        self.description = f"""
Not everything that needs scheduling repeats. Create a playbook
at_job.yml  in your working directory ({self.workdir}) that, on ALL
managed nodes, uses the  ansible.posix.at  module (install
ansible-galaxy collection install ansible.posix if needed — it should
already be present) to schedule a ONE-TIME job, {minutes} minutes from
now, that creates the file  {marker} .

Do NOT use the cron module — this must be a genuine  at  job (queued via
atd), confirmed present in the  at  queue after the playbook runs.
"""
        self.hints = [
            "ansible.posix.at: command: 'touch " + marker + "'  count: " +
            str(minutes) + "  units: minutes",
            "atd must be running on the managed node for at jobs to fire "
            "— the module itself doesn't start the service for you.",
            "Confirm what's queued with: atq  (lists pending at jobs by "
            "job number).",
        ]
        self.exam_tips = [
            "cron is for RECURRING schedules; at is for 'run this once, "
            "later'. Reaching for cron with a job that deletes itself "
            "after one run is the wrong tool and a common exam mistake.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "at_job.yml",
                            r"(ansible\.posix\.)?at\s*:",
                            "playbook uses the at module")
        self.check_contains(res, "at_job.yml", self.params["marker"],
                            "scheduled command references the marker file")
        if not self.check_playbook_runs(res, "at_job.yml",
                                        require_idempotent=False):
            return res
        self.check_node_state(res, "atd is running (jobs can actually fire)",
                              "all", "ansible.builtin.command",
                              "systemctl is-active atd", expect=r"\bactive\b",
                              become=True)
        self.check_node_state(res, "a job is queued in the at queue",
                              "all", "ansible.builtin.command", "atq",
                              expect=r"\S+", become=True)
        return res
