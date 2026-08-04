"""Domain 7: storage automation."""

import random
import re

from config import settings
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


# Attaching a spare blank disk is a manual, lab-specific step, so state
# checks only run on nodes that actually have one.
NO_SPARE_DISK = (
    "No managed node currently has an unpartitioned spare disk at the "
    "target device, so the end state couldn't be observed — your playbook "
    "was still graded on content, on running cleanly, and on correctly "
    "SKIPPING hosts without the disk, which is the real skill here.\n"
    "To grade the full chain, attach a spare virtual disk to a lab VM "
    "(e.g. a second 10G disk in VMware/virt-manager) and re-validate."
)


@TaskRegistry.register("storage_auto")
class DiskToMountedFilesystemTask(AnsibleTask):
    """Blank disk -> partition -> PV/VG/LV -> filesystem -> persistent mount,
    gated on the disk actually being present."""

    def __init__(self):
        super().__init__("stor_disk_chain_001", "storage_auto", "hard")

    def generate(self, **params):
        device = params.get("device") or settings.get_spare_disk()
        vg, lv = "data_vg", "data_lv"
        size = params.get("size") or random.choice([800, 1000, 1200])
        mount = params.get("mount") or "/data"
        self.params = {"device": device, "short": device.split("/")[-1],
                       "vg": vg, "lv": lv, "size": size, "mount": mount}
        p = self.params
        self.description = f"""
Some of your managed nodes have been given a spare blank disk at
{device} ; others have not. Build the whole storage stack on the ones that
do, and cleanly skip the ones that don't.

Create a playbook  disk_setup.yml  in your working directory
({self.workdir}) that runs against ALL managed nodes and:

  1. ONLY acts on hosts that actually have {device} — detect this from
     gathered facts, do not hard-code a hostname
  2. creates a GPT partition table on {device} with a single 1 GiB partition
  3. builds a volume group  {p['vg']}  on that partition
  4. creates a logical volume  {p['lv']}  of {p['size']} MiB inside it
  5. formats {p['lv']} as  ext4
  6. mounts it at  {p['mount']}  and makes the mount PERSISTENT across reboots

The playbook must complete successfully on every host — including the ones
with no spare disk, which must simply skip these tasks rather than fail.

!! This partitions a disk. Only ever run it against a disposable lab VM
   or container. Never point it at a machine holding data you care about.
"""
        self.hints = [
            "Detect the disk with: when: \"'{}' in ansible_facts['devices']\" "
            "(gather_facts must be on).".format(p["short"]),
            "community.general.parted — device:, number: 1, state: present, "
            "label: gpt, part_end: 1GiB.",
            "community.general.lvg (pvs: {}1 creates the PV for you), then "
            "community.general.lvol, then community.general.filesystem."
            .format(device),
            "ansible.posix.mount with state: mounted writes /etc/fstab AND "
            "mounts now — state: present only writes fstab.",
            "Wrap the whole chain in one block: with a single when: so you "
            "write the condition once instead of on every task.",
        ]
        self.exam_tips = [
            "state: mounted vs state: present is a classic trap — 'present' "
            "leaves the filesystem unmounted until the next reboot, so a "
            "grader checking `mount` right now sees nothing.",
            "Hard-coding hosts: the-node-with-the-disk instead of using a "
            "fact condition defeats the point and is marked wrong even "
            "though the end state looks right.",
        ]
        return self

    def validate(self):
        res = self.result()
        p = self.params
        self.check_contains(res, "disk_setup.yml",
                            r"(community\.general\.)?parted\s*:",
                            "playbook partitions the disk with parted")
        self.check_contains(res, "disk_setup.yml", r"label:\s*gpt",
                            "GPT partition table requested")
        self.check_contains(res, "disk_setup.yml",
                            r"(community\.general\.)?lvg\s*:",
                            "volume group created")
        self.check_contains(res, "disk_setup.yml",
                            r"(community\.general\.)?lvol\s*:",
                            "logical volume created")
        self.check_contains(res, "disk_setup.yml",
                            r"(community\.general\.)?filesystem\s*:",
                            "filesystem created")
        self.check_contains(res, "disk_setup.yml", r"ext4",
                            "filesystem type is ext4")
        self.check_contains(res, "disk_setup.yml", r"state:\s*mounted",
                            "mounted persistently (state: mounted writes fstab)")
        self.check_contains(res, "disk_setup.yml",
                            rf"when:[\s\S]{{0,120}}(devices|{p['short']})",
                            "acts only on hosts that have the disk (fact-based)")
        if not self.check_playbook_runs(res, "disk_setup.yml"):
            return res
        # Only nodes with a real spare disk can demonstrate the end state.
        if not self.probe("ansible.builtin.command",
                          f"test -b {p['device']}", become=True,
                          require_all=False):
            res.add_skip(f"{p['mount']} ends up mounted from {p['lv']}",
                         NO_SPARE_DISK)
            return res
        # Each check short-circuits to success on hosts with no spare disk,
        # so "correctly skipped" and "correctly built" both pass — which is
        # exactly what the task asked for.
        guard = f"test -b {p['device']} || exit 0; "
        self.check_node_state(res, f"{p['lv']} exists in {p['vg']}", "all",
                              "ansible.builtin.shell",
                              guard + f"lvs --noheadings -o lv_name,vg_name "
                                      f"| grep -q {p['lv']}",
                              become=True)
        self.check_node_state(res, f"{p['mount']} is mounted as ext4", "all",
                              "ansible.builtin.shell",
                              guard + f"findmnt -no FSTYPE {p['mount']} "
                                      f"| grep -q ext4",
                              become=True)
        self.check_node_state(res, f"{p['mount']} is recorded in /etc/fstab",
                              "all", "ansible.builtin.shell",
                              guard + f"grep -q {p['mount']} /etc/fstab",
                              become=True)
        return res


@TaskRegistry.register("storage_auto")
class SwapFileTask(AnsibleTask):
    """File-based swap: no spare disk required, unlike the LVM chain — a
    genuinely different (and much more commonly usable) storage pattern."""

    def __init__(self):
        super().__init__("stor_swapfile_001", "storage_auto", "medium")

    def generate(self, **params):
        size_mb = params.get("size_mb") or random.choice([256, 512])
        self.params = {"path": "/swapfile", "size_mb": size_mb}
        self.description = f"""
Create a playbook  swapfile.yml  in your working directory
({self.workdir}) that, on ALL managed nodes, creates and activates a
file-based swap area:

  * file:  {self.params['path']} , exactly  {size_mb}  MiB, mode 0600
  * formatted as swap and turned ON right now
  * recorded in  /etc/fstab  so it survives a reboot

Idempotent — a second run must not recreate the file or add a duplicate
fstab entry.
"""
        self.hints = [
            "ansible.builtin.command with creates: to allocate the file "
            "exactly once (fallocate -l " + f"{size_mb}M {self.params['path']}"
            + ") — command/shell tasks need creates: or they run every "
            "time.",
            "file: path: ... mode: '0600' — a world-readable swapfile is "
            "a real (if minor) security bug, and graders check for it.",
            "community.general.filesystem: fstype: swap, dev: " +
            self.params["path"],
            "ansible.posix.mount with fstype: swap needs state: mounted "
            "won't apply — swap uses swapon; use the mount module ONLY "
            "for the fstab entry (state: present), then activate "
            "separately with the command module and creates:/a check.",
        ]
        self.exam_tips = [
            "Swap doesn't 'mount' in the filesystem sense — state: "
            "mounted (which works for regular filesystems) doesn't "
            "activate swap. You still need swapon, driven by a command "
            "task or the fstab entry plus a reboot.",
        ]
        return self

    def validate(self):
        res = self.result()
        p = self.params
        self.check_contains(res, "swapfile.yml", r"mode:\s*[\"']?0?600",
                            "swapfile is created with mode 0600")
        self.check_contains(res, "swapfile.yml", r"fstype:\s*swap",
                            "filesystem is formatted as swap")
        self.check_contains(res, "swapfile.yml", p["path"],
                            f"playbook targets {p['path']}")
        if not self.check_playbook_runs(res, "swapfile.yml"):
            return res
        self.check_node_state(res, f"{p['path']} exists at {p['size_mb']}MiB", "all",
                              "ansible.builtin.shell",
                              f"stat -c %s {p['path']} | awk '{{print int($1/1048576)}}'",
                              expect=rf"\b{p['size_mb']}\b", become=True)
        self.check_node_state(res, f"{p['path']} is active swap", "all",
                              "ansible.builtin.shell", "swapon --show=NAME",
                              expect=re.escape(p["path"]), become=True)
        self.check_node_state(res, f"{p['path']} is recorded in /etc/fstab", "all",
                              "ansible.builtin.command",
                              f"grep -q {p['path']} /etc/fstab && echo FOUND",
                              expect=r"FOUND", become=True)
        return res


@TaskRegistry.register("storage_auto")
class BindMountTask(AnsibleTask):
    """Bind mounts: exposing one directory at a second path — no new
    filesystem, no spare disk, just the mount table."""

    def __init__(self):
        super().__init__("stor_bindmount_001", "storage_auto", "medium")

    def generate(self, **params):
        source = params.get("source") or random.choice(
            ["/opt/shared_content", "/srv/shared_assets"])
        target = params.get("target") or random.choice(
            ["/var/www/html/shared", "/opt/www_shared"])
        marker = "bindmount_probe.txt"
        self.params = {"source": source, "target": target, "marker": marker}
        self.description = f"""
Create a playbook  bindmount.yml  in your working directory
({self.workdir}) that, on ALL managed nodes:

  1. creates the source directory  {source}  and places a file
     {marker}  inside it (any content)
  2. creates the target directory  {target}
  3. BIND-MOUNTS  {source}  onto  {target}  — the same content must be
     readable at BOTH paths — and makes the bind mount PERSISTENT across
     reboots

Idempotent.
"""
        self.hints = [
            "ansible.posix.mount: path: " + target + "  src: " + source +
            "  opts: bind  fstype: none  state: mounted",
            "A bind mount has no filesystem type of its own — fstype: "
            "none is correct and expected, not a placeholder.",
            "state: mounted (not present) both activates the bind now AND "
            "writes the persistent fstab entry.",
        ]
        return self

    def validate(self):
        res = self.result()
        p = self.params
        self.check_contains(res, "bindmount.yml", r"opts:.*bind",
                            "playbook uses a bind mount (opts: bind)")
        self.check_contains(res, "bindmount.yml", r"state:\s*mounted",
                            "mount is active now and persisted (state: mounted)")
        if not self.check_playbook_runs(res, "bindmount.yml"):
            return res
        self.check_node_state(res, f"{p['target']}/{p['marker']} is visible via the bind mount",
                              "all", "ansible.builtin.command",
                              f"test -e {p['target']}/{p['marker']}", become=True)
        self.check_node_state(res, f"{p['target']} is recorded in /etc/fstab", "all",
                              "ansible.builtin.shell",
                              f"grep -q {p['target']} /etc/fstab && echo FOUND",
                              expect=r"FOUND", become=True)
        return res
