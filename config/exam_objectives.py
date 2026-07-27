"""
Official EX294 study points, grouped by simulator domain.

Source: the canonical Red Hat exam page (checked 2026-07-23, re-verified
against primary sources 2026-07-27):
https://www.redhat.com/en/services/training/ex294-red-hat-certified-engineer-rhce-exam-red-hat-enterprise-linux
Every legacy per-RHEL-version URL now redirects to this single evergreen
page — Red Hat states, verbatim: "Objectives listed for this exam are
based on the most recent Red Hat product version available."

Version alignment, stated precisely because it's easy to overclaim: the
exam page itself names NO RHEL or Ansible version. RHEL 10 is the current
release and ships ansible-core 2.16 plus the rhel-system-roles RPM (Red
Hat RHEL 10 documentation, "Automating system administration by using
RHEL system roles"). So "EX294 targets RHEL 10 / ansible-core 2.16" is a
sound inference from the evergreen-objectives wording plus the current
product, NOT something Red Hat states about the exam. Treat it as such.

Domain numbering below matches the official page's own 11 domains, not an
earlier internal renumbering. Re-verified 2026-07-27 as still current:
Visual Studio Code, ansible-navigator, Ansible development containers
(execution environments) and Git source control are all genuinely on the
published objectives list — these are frequently missing from third-party
prep material and are not this project's invention.

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

Verified against primary sources 2026-07-27:
  * The exam page's own title is "Red Hat Certified Advanced System
    Administrator in Ansible Exam (EX294)" — CONFIRMED.
  * Passing EX294 alone makes you "a Red Hat Certified Advanced System
    Administrator in Ansible", which then "counts towards earning" RHCE
    in Ansible and RHCA — CONFIRMED, so the standalone-credential claim
    above is right.
  * The stacked RHCE credential ("Red Hat Certified Engineer in Ansible",
    redhat.com/en/services/certification/rhce) still lists BOTH EX200 and
    EX294 as required. RHCSA is therefore not a prerequisite for the
    EX294 credential, but IS still required for RHCE itself. Both halves
    matter — don't collapse them.
  * The May 11 2026 date and the "content/difficulty unchanged" quote are
    NOT confirmed from a primary source; they remain second-hand.
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
# Verified verbatim on the official page 2026-07-27: "As with all Red Hat
# performance-based exams, configurations must persist after reboot
# without intervention."
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
    "score for EX294 — re-checked 2026-07-27, and none of the three "
    "appears on the official exam page. The EX200 (RHCSA) page doesn't "
    "publish them either, so this isn't an EX294 oversight: it's Red Hat's "
    "current practice across performance exams. What IS well attested "
    "(Red Hat Learning Community, not the exam pages) is that results come "
    "back as a total on a 0-300 scale with 210 to pass — which is the same "
    "bar as this simulator's 70%. The 4-hour and ~20-task figures are "
    "community consensus only. Treat all of it as pacing practice, not as "
    "the official bar."
)
