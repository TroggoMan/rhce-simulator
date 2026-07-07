"""Domain 7: storage automation."""

import random

from core.registry import TaskRegistry
from tasks.base import AnsibleTask


@TaskRegistry.register("storage_auto")
class LvmConditionalTask(AnsibleTask):
    """The infamous EX294 LVM task, defensive-coding edition."""

    def __init__(self):
        super().__init__("stor_lvm_001", "storage_auto", "hard")

    def generate(self, **params):
        size, fallback = params.get("sizes") or random.choice(
            [(1500, 800), (1200, 600), (2000, 1000)])
        self.params = {"vg": "research", "lv": "data",
                       "size": size, "fallback": fallback}
        self.description = f"""
Create a playbook  lvm.yml  in your working directory ({self.workdir})
that runs on ALL managed nodes and:

  * if the volume group  research  exists:
      - create a logical volume  data  of {size} MiB in it
      - if there is not enough space, print the message
        "Could not create logical volume of that size"  and create it
        with {fallback} MiB instead
  * if the volume group does NOT exist, print the message
        "Volume group does not exist"
  * the playbook must NEVER fail, on any node, whether or not the VG
    or enough space exists.

(Nodes without a 'research' VG are fine — the messages path still grades.)
"""
        self.hints = [
            "ansible_facts['lvm']['vgs'] shows existing VGs (needs setup/gather).",
            "community.general.lvol for the LV; block/rescue or when: chains both work.",
            "Sizes in the vgs fact are strings — compare with | float or | int.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "lvm.yml", r"(lvol|lvcreate)",
                            "playbook creates a logical volume")
        self.check_contains(res, "lvm.yml", r"Volume group does not exist",
                            "missing-VG message present")
        self.check_contains(res, "lvm.yml", r"Could not create logical volume",
                            "not-enough-space message present")
        self.check_playbook_runs(res, "lvm.yml", require_idempotent=False)
        return res


@TaskRegistry.register("storage_auto")
class TmpfsMountTask(AnsibleTask):
    def __init__(self):
        super().__init__("stor_mount_001", "storage_auto", "medium")

    def generate(self, **params):
        point = params.get("point") or random.choice(
            ["/mnt/simcache", "/mnt/fastscratch"])
        size = params.get("size") or random.choice(["256m", "512m"])
        self.params = {"point": point, "size": size}
        self.description = f"""
Create a playbook  mount.yml  in your working directory ({self.workdir})
that, on ALL managed nodes, persistently mounts a tmpfs filesystem:

  * mount point:  {point}   (create it)
  * size option:  {size}
  * must be recorded in /etc/fstab AND mounted right now

Idempotent.
"""
        self.hints = [
            "ansible.posix.mount with src: tmpfs, fstype: tmpfs, opts: size=" + size,
            "state: mounted both mounts it and writes fstab.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "mount.yml", r"mount\s*:|ansible\.posix\.mount",
                            "playbook uses the mount module")
        if not self.check_playbook_runs(res, "mount.yml"):
            return res
        point = self.params["point"]
        self.check_node_state(res, f"tmpfs mounted on {point}",
                              "all", "ansible.builtin.command",
                              f"findmnt -t tmpfs {point}", become=True)
        self.check_node_state(res, f"{point} present in /etc/fstab",
                              "all", "ansible.builtin.command",
                              f"grep {point} /etc/fstab", become=True)
        return res
