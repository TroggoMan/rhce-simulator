"""
Global settings for the RHCE EX294 (RHEL 10) exam simulator.

Sibling project to rhcsa-simulator and follows the same conventions:
Python standard library only, tasks auto-discovered from tasks/, validators
run real commands (here: ansible-core CLI tools) and never mutate state
themselves — all system changes are made by the candidate's own playbooks.
"""

import os
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


# Managed nodes the lab has available. Comma-separated hostnames/IPs in
# RHCE_SIM_NODES; defaults to localhost so the simulator is usable on a
# single VM (inventory entries can use ansible_connection=local).
def get_nodes() -> list:
    raw = os.environ.get("RHCE_SIM_NODES", "localhost")
    return [n.strip() for n in raw.split(",") if n.strip()]


# The user Ansible connects as on managed nodes (exam convention: a devops
# user with passwordless sudo). Only used in task descriptions.
REMOTE_USER = os.environ.get("RHCE_SIM_REMOTE_USER", "devops")

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
