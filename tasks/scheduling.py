"""Domain 7: task scheduling automation."""

import random

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
