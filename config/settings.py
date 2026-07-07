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

# EX294 is 4 hours, pass mark 210/300 (70%).
EXAM_DURATION_MINUTES = 240
PASS_PERCENT = 70
EXAM_TASK_COUNT = 15
QUICK_TASK_COUNT = 5

# Objective domains (config/exam_objectives.py has the full study points).
EXAM_DOMAINS = {
    1: "Configure Ansible and managed nodes",
    2: "Run playbooks (ansible-playbook, ansible-navigator, EEs)",
    3: "Author plays and playbooks",
    4: "Templates and managed files",
    5: "Roles and Content Collections",
    6: "Ansible Vault",
    7: "Automate RHCSA administration tasks",
}

CATEGORY_TO_DOMAIN = {
    "ansible_config": 1,
    "inventory": 1,
    "adhoc": 2,
    "navigator": 2,
    "playbook_basics": 3,
    "variables_facts": 3,
    "flow_control": 3,
    "error_handling": 3,
    "templates": 4,
    "file_content": 4,
    "roles": 5,
    "system_roles": 5,
    "collections": 5,
    "vault": 6,
    "storage_auto": 7,
    "users_auto": 7,
    "scheduling_auto": 7,
}

CATEGORY_DISPLAY = {
    "ansible_config": "Ansible & Navigator Configuration",
    "inventory": "Inventories & Host Groups",
    "adhoc": "Ad-hoc Commands",
    "navigator": "Automation Content Navigator",
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
