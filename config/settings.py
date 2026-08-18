"""
Global settings for the RHCE EX294 (RHEL 10) exam simulator.

Sibling project to rhcsa-simulator and follows the same conventions:
Python standard library only, tasks auto-discovered from tasks/, validators
run real commands (here: ansible-core CLI tools) and never mutate state
themselves — all system changes are made by the candidate's own playbooks.
"""

import os
import subprocess
import sys
from pathlib import Path

VERSION = "0.1.0"
EXAM_NAME = "RHCE EX294 (RHEL 10)"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Repo root (this file lives in config/).
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DB = DATA_DIR / "results.db"

# The candidate's Ansible working directory — where ansible.cfg, inventory,
# playbooks, roles/ and collections/ are expected to live. Mirrors the real
# exam, where all work happens in one directory on the control node.
def get_workdir() -> Path:
    return Path(os.environ.get("RHCE_SIM_WORKDIR", "~/ansible")).expanduser()


# The fixed hostnames both lab builders use (docker/docker-compose.yml
# container_name: / vagrant/Vagrantfile), in the order lab-setup.sh brings
# them up. "control" is deliberately excluded — it's the machine you work
# FROM, never a managed node.
_LAB_NODE_NAMES = ["kirk", "spock", "mccoy", "scotty"]

# Detected once per process and cached — both lab checks shell out, and
# nodes is read on every task (see tasks/base.py:AnsibleTask.nodes), so
# re-running them per call would make every task construction pay a
# subprocess cost. Sentinel None means "not attempted yet"; [] is a valid
# (negative) result.
_detected_nodes_cache = None


def _detect_docker_nodes() -> list:
    try:
        proc = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=3, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    running = set(proc.stdout.split())
    return [n for n in _LAB_NODE_NAMES if n in running]


def _detect_vagrant_nodes() -> list:
    vagrant_dir = BASE_DIR / "vagrant"
    if not vagrant_dir.is_dir():
        return []
    try:
        proc = subprocess.run(
            ["vagrant", "status", "--machine-readable"],
            capture_output=True, text=True, timeout=5, check=True,
            cwd=vagrant_dir, env={**os.environ, "VAGRANT_CWD": str(vagrant_dir)},
        )
    except (OSError, subprocess.SubprocessError):
        return []
    running = set()
    for line in proc.stdout.splitlines():
        # <timestamp>,<target>,state,<value> e.g. "...,kirk,state,running"
        fields = line.split(",")
        if len(fields) >= 4 and fields[2] == "state" and fields[3] == "running":
            running.add(fields[1])
    return [n for n in _LAB_NODE_NAMES if n in running]


def _detect_lab_nodes() -> list:
    """Best-effort discovery of a running lab, tried only when the
    candidate hasn't set RHCE_SIM_NODES themselves. Docker first (cheap,
    common case), then Vagrant. Returns [] — never raises — if neither
    tool is present or nothing is running, so callers fall back to
    localhost exactly as before this existed."""
    return _detect_docker_nodes() or _detect_vagrant_nodes()


def detect_lab_type_and_nodes() -> tuple:
    """Like _detect_lab_nodes, but also reports which tool found them.
    Docker and Vagrant expose managed nodes differently (fixed
    127.0.0.1:220x ports vs. a real per-VM IP on port 22), so UX that
    needs to show a candidate live connection details — --setup — has to
    know which one it's looking at. Returns (None, []) if nothing's
    running."""
    docker_nodes = _detect_docker_nodes()
    if docker_nodes:
        return "docker", docker_nodes
    vagrant_nodes = _detect_vagrant_nodes()
    if vagrant_nodes:
        return "vagrant", vagrant_nodes
    return None, []


# Managed nodes the lab has available. RHCE_SIM_NODES (comma-separated
# hostnames/IPs) always wins when set — that's how you point the simulator
# at your own machines (Option 3 in the README) or override the detected
# list. Left unset, we try to detect a running lab lab-setup.sh /
# vm-lab-setup.sh built (see _detect_lab_nodes) so a fresh install works
# without an export; finding nothing, we fall back to localhost so the
# simulator still runs standalone (inventory entries can use
# ansible_connection=local).
def get_nodes() -> list:
    global _detected_nodes_cache
    raw = os.environ.get("RHCE_SIM_NODES")
    if raw:
        return [n.strip() for n in raw.split(",") if n.strip()]

    if _detected_nodes_cache is None:
        _detected_nodes_cache = _detect_lab_nodes()
        if _detected_nodes_cache:
            print(
                f"(detected running lab nodes: {', '.join(_detected_nodes_cache)} "
                "— set RHCE_SIM_NODES to override)",
                file=sys.stderr,
            )

    return _detected_nodes_cache or ["localhost"]


# The user Ansible connects as on managed nodes (exam convention: a devops
# user with passwordless sudo). Only used in task descriptions.
REMOTE_USER = os.environ.get("RHCE_SIM_REMOTE_USER", "devops")


# The spare block device the storage task partitions, if the lab has one.
# Device naming depends entirely on the virtual disk bus, and getting it
# wrong is silently harmful: the task would name a device that doesn't
# exist, the candidate's (correct) fact-based condition would skip every
# task, and they'd pass the file checks having changed nothing.
#   KVM/libvirt + virtio -> /dev/vdb   (this project's VM lab, and what
#                                       Red Hat's own exam VMs typically use)
#   VirtualBox/SATA, SCSI -> /dev/sdb
# scripts/vm-lab-setup.sh detects the real device and prints the matching
# export line, so normally you never set this by hand.
def get_spare_disk() -> str:
    return os.environ.get("RHCE_SIM_SPARE_DISK", "/dev/vdb")

# ---------------------------------------------------------------------------
# Exam structure
# ---------------------------------------------------------------------------

# Red Hat does not publish exam duration, task count, or a numeric pass
# score for EX294 (confirmed by checking the current official page
# 2026-07-23 — it states only Pass/Fail plus an objective-based breakdown).
# These are long-standing, widely-repeated community-consensus figures used
# here to make practice sessions feel realistic — see
# exam_objectives.UNPUBLISHED_NUMBERS_NOTE, shown in --learn mode.
EXAM_DURATION_MINUTES = 240
PASS_PERCENT = 70
EXAM_TASK_COUNT = 20
QUICK_TASK_COUNT = 5

# Red Hat reports performance-exam results as a total score on a 0-300
# scale, with 210 the long-established pass threshold (210/300 == 70%, so
# this is consistent with PASS_PERCENT above rather than a second opinion).
# Sourcing, checked 2026-07-27: neither the current EX294 page NOR the
# current EX200 page publishes a scale or a pass mark — the 300-point scale
# and the 210 threshold are attested in Red Hat Learning Community
# discussion (learn.redhat.com), not on the exam pages themselves. Shown
# alongside the raw points so the number resembles what Certification
# Central actually hands you, but see UNPUBLISHED_NUMBERS_NOTE: do not
# treat it as an official figure.
RH_SCORE_SCALE = 300
RH_PASS_SCORE = 210

# Objective domains, renumbered 2026-07-23 to match the official page's own
# 11 domains exactly (see config/exam_objectives.py for sourcing and the
# full bullet points) rather than an earlier internal 7-domain grouping.
# Domains 1 and 4 have no dedicated simulator category: domain 1 (RHCSA
# foundation) is the sibling rhcsa-simulator's job; domain 4's SSH-key/
# privilege-escalation setup is what managed_nodes below actually drills.
EXAM_DOMAINS = {
    1: "RHCSA foundation (prerequisite skills)",
    2: "Core Ansible components",
    3: "Configure Ansible",
    4: "Configure managed nodes",
    5: "Run playbooks (ansible-navigator, ansible-playbook)",
    6: "Source control with Git",
    7: "VS Code & execution environments",
    8: "Create plays and playbooks",
    9: "Roles and Content Collections",
    10: "Automate RHCSA tasks with Ansible",
    11: "Manage content (templates, Vault)",
}

CATEGORY_TO_DOMAIN = {
    "ansible_config": 3,
    "inventory": 3,
    "managed_nodes": 4,
    "adhoc": 2,
    "navigator": 5,
    "source_control": 6,
    "playbook_basics": 8,
    "variables_facts": 8,
    "flow_control": 8,
    "error_handling": 8,
    "templates": 11,
    "file_content": 10,
    "roles": 9,
    "system_roles": 9,
    "collections": 9,
    "vault": 11,
    "storage_auto": 10,
    "users_auto": 10,
    "scheduling_auto": 10,
    "selinux": 10,
}

# Order tasks are PRESENTED in within a session. The domain number is
# already the right sequence in almost every case — configure Ansible (3)
# and the managed nodes (4) before running anything (5), writing plays (8)
# or reaching roles (9) and the RHCSA-automation domains (10-11). The
# exception is a domain taught early that in practice depends on later
# setup: ad-hoc commands are domain 2 ("core components"), but you cannot
# run one without the inventory and node access built in domains 3-4, so
# they sort just after those rather than opening a session.
CATEGORY_SEQUENCE_OVERRIDE = {"adhoc": 4.5}


def sequence_rank(category):
    """Sort key placing setup categories ahead of the work that needs them."""
    if category in CATEGORY_SEQUENCE_OVERRIDE:
        return CATEGORY_SEQUENCE_OVERRIDE[category]
    return CATEGORY_TO_DOMAIN.get(category, max(EXAM_DOMAINS) + 1)


CATEGORY_DISPLAY = {
    "ansible_config": "Ansible & Navigator Configuration",
    "inventory": "Inventories & Host Groups",
    "managed_nodes": "SSH Keys & Privilege Escalation",
    "adhoc": "Ad-hoc Commands",
    "navigator": "Automation Content Navigator",
    "source_control": "Git Source Control",
    "playbook_basics": "Playbook Basics",
    "variables_facts": "Variables & Facts",
    "flow_control": "Loops & Conditionals",
    "error_handling": "Handlers & Error Handling",
    "templates": "Jinja2 Templates",
    "file_content": "File Content & Archiving",
    "roles": "Roles",
    "system_roles": "RHEL System Roles",
    "collections": "Content Collections",
    "vault": "Ansible Vault",
    "storage_auto": "Storage Automation",
    "users_auto": "Users & Groups Automation",
    "scheduling_auto": "Scheduling Automation",
    "selinux": "SELinux Automation",
}

DIFFICULTY_POINTS = {"easy": 10, "medium": 20, "hard": 30}

# ---------------------------------------------------------------------------
# Terminal colors
# ---------------------------------------------------------------------------

USE_COLOR = os.environ.get("NO_COLOR") is None


class C:
    RESET = "\033[0m" if USE_COLOR else ""
    BOLD = "\033[1m" if USE_COLOR else ""
    RED = "\033[31m" if USE_COLOR else ""
    GREEN = "\033[32m" if USE_COLOR else ""
    YELLOW = "\033[33m" if USE_COLOR else ""
    BLUE = "\033[34m" if USE_COLOR else ""
    CYAN = "\033[36m" if USE_COLOR else ""
    DIM = "\033[2m" if USE_COLOR else ""
