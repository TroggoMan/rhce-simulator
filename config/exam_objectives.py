"""
Official EX294 study points, grouped by simulator domain.

Source: the canonical Red Hat exam page (checked 2026-07-23):
https://www.redhat.com/en/services/training/ex294-red-hat-certified-engineer-rhce-exam-red-hat-enterprise-linux
Every legacy per-RHEL-version URL now redirects to this single evergreen
page — Red Hat states objectives "are based on the most recent Red Hat
product version available" rather than pinning a RHEL number, and as of
this check the aligned platform is RHEL 10 (Ansible Core 2.16, per Red
Hat's AU294 course page). Domain numbering below matches the official
page's own 11 domains, not an earlier internal renumbering.

Naming note: as part of a May 11, 2026 restructure of the whole Red Hat
certification catalog, EX294's official title changed from "Red Hat
Certified Engineer (RHCE) exam" to "Red Hat Certified Advanced System
Administrator in Ansible Exam" — Red Hat states this is a naming/structural
change only ("the content, descriptions, and difficulty remain exactly the
same"). RHCE is now a stacked title earned via this exam rather than the
exam's own name; passing EX294 alone (without RHCSA) now also yields a
standalone credential, which it did not before. "RHCE" is kept as this
project's name because it's still the name almost everyone searches for
and uses day to day.
"""

OBJECTIVES = {
    1: [
        "Be able to perform all tasks expected of a Red Hat Certified "
        "System Administrator (RHCSA) — essential tools, running systems, "
        "local storage, file systems, deploying/configuring/maintaining "
        "systems, users and groups, security",
        "Be able to analyze simple shell scripts",
    ],
    2: [
        "Understand core components of Ansible: inventories, modules, "
        "variables, facts, loops, conditional tasks, plays, handling task "
        "failure, playbooks, configuration files, roles",
        "Use provided documentation to look up specific information about "
        "Ansible modules and commands",
    ],
    3: [
        "Create and modify an ansible.cfg configuration file",
        "Modify an ansible-navigator.yml configuration file",
        "Create a static host inventory file",
        "Create and use static inventories to define groups of hosts",
    ],
    4: [
        "Create and distribute SSH keys to managed nodes",
        "Configure privilege escalation on managed nodes",
        "Deploy files to managed nodes",
    ],
    5: [
        "Know how to run playbooks with ansible-navigator and "
        "ansible-playbook",
        "Use ansible-navigator to find new modules in available Ansible "
        "Content Collections and use them",
        "Use ansible-navigator to create inventories and configure the "
        "Ansible environment",
    ],
    6: [
        "Perform basic source control operations using Git",
        "Clone a Git repository",
        "Add files to a Git repository",
    ],
    7: [
        "Be familiar with Visual Studio Code (VS Code) and be able to "
        "perform the following tasks from within the editor:",
        "  create playbooks and push them to a Git repository",
        "  configure ansible-navigator",
        "  run playbooks using an Ansible development container "
        "(execution environment)",
    ],
    8: [
        "Know how to work with commonly used Ansible modules",
        "Use variables to retrieve the results of running a command "
        "(register)",
        "Use conditionals to control play execution",
        "Configure error handling",
        "Create playbooks to configure systems to a specified state",
    ],
    9: [
        "Create and work with roles",
        "Install roles and use them in playbooks",
        "Install Content Collections and use them in playbooks",
        "Obtain a set of related roles, supplementary modules, and other "
        "content from content collections, and use them in a playbook "
        "(including RHEL System Roles)",
    ],
    10: [
        "Automate standard RHCSA tasks using Ansible modules that work with:",
        "  software packages and repositories",
        "  services",
        "  firewall rules",
        "  file systems",
        "  storage devices (partitions, LVM)",
        "  file content",
        "  archiving",
        "  task scheduling",
        "  security (SELinux modes, booleans, file contexts)",
        "  users and groups",
    ],
    11: [
        "Create and use templates to create customized configuration files",
        "Use Ansible Vault in playbooks to protect sensitive data",
    ],
}

# Every Red Hat performance exam shares this requirement; it isn't listed
# as a numbered objective but is stated as a standalone note on the page.
PERSISTENCE_NOTE = (
    "As with all Red Hat performance-based exams, configurations must "
    "persist after reboot without intervention. A playbook that only works "
    "until the next reboot doesn't pass — enable services, don't just start "
    "them; write to /etc/fstab, don't just mount."
)

# Prerequisite reminder shown in --learn mode.
FOUNDATION_NOTE = (
    "EX294 also assumes full RHCSA (EX200) competence — essential tools, "
    "running systems, local storage, file systems, users/groups, security. "
    "Use the sibling rhcsa-simulator project to drill those. Note: since "
    "the May 2026 restructure, RHCSA is no longer a hard prerequisite for "
    "a credential (passing EX294 alone now grants a standalone Ansible "
    "specialist certification) — but the RHCSA skills are still exercised "
    "throughout EX294 itself (see Domain 1 and Domain 10), so skipping "
    "them is not a shortcut."
)

# Numbers Red Hat does NOT publish on the official page (duration, task
# count, pass score). Long-standing, consistent third-party consensus is
# quoted here for realism, but flagged as unverified against a primary
# source — shown in --learn mode so nobody mistakes them for official.
UNPUBLISHED_NUMBERS_NOTE = (
    "Red Hat does not publish exam duration, task count, or a numeric pass "
    "score for EX294 — the official page states only that scoring is "
    "Pass/Fail plus an objective-based breakdown. This simulator's 4-hour, "
    "~20-task, 70%-pass defaults are long-standing, widely-repeated "
    "community consensus, not confirmed Red Hat figures."
)
