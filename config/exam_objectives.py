"""
Official EX294 (RHEL 10) study points, grouped by simulator domain.

Source: Red Hat exam page ("Red Hat Certified Engineer (RHCE) exam",
objectives based on the most recent RHEL version — RHEL 10.0 with
ansible-core and automation content navigator). Used by --learn mode.
"""

OBJECTIVES = {
    1: [
        "Create and modify an ansible.cfg configuration file",
        "Create and modify an ansible-navigator.yml configuration file",
        "Create a static host inventory file and define groups of hosts",
        "Distribute SSH keys to managed nodes",
        "Configure privilege escalation on managed nodes",
        "Deploy files to managed nodes",
    ],
    2: [
        "Know how to run playbooks with ansible-navigator and ansible-playbook",
        "Use ansible-navigator to find new modules in available Ansible "
        "Content Collections and use them",
        "Use ansible-navigator to create inventories and configure the "
        "Ansible environment",
        "Run playbooks using an Ansible development container "
        "(execution environment)",
        "Analyze simple shell scripts and convert them to playbooks",
    ],
    3: [
        "Understand core components of Ansible: inventories, modules, "
        "variables, facts, loops, conditional tasks, plays, playbooks, "
        "handling task failure, configuration files, roles",
        "Use variables to retrieve the results of running a command "
        "(register)",
        "Use conditionals to control play execution",
        "Configure error handling (ignore_errors, blocks, rescue, always)",
        "Use Ansible documentation to look up specific modules and commands",
    ],
    4: [
        "Create and use templates to create customized configuration files",
        "Manage file content and deploy files to managed nodes",
        "Archive, compress and extract files with Ansible modules",
    ],
    5: [
        "Create and work with roles",
        "Install roles and use them in playbooks",
        "Install Content Collections and use them in playbooks "
        "(including RHEL System Roles)",
        "Obtain a set of related roles, supplementary modules, and other "
        "content from content collections",
    ],
    6: [
        "Use Ansible Vault in playbooks to protect sensitive data",
        "Create, edit, encrypt, decrypt and view vault-protected files",
    ],
    7: [
        "Automate standard RHCSA tasks using Ansible modules that work with:",
        "  software packages and repositories",
        "  services",
        "  firewall rules",
        "  file systems, storage devices (partitions, LVM)",
        "  file content",
        "  archiving",
        "  task scheduling (cron, at)",
        "  security (SELinux modes, booleans, file contexts)",
        "  users and groups",
    ],
}

# Prerequisite reminder shown in --learn mode.
FOUNDATION_NOTE = (
    "EX294 also assumes full RHCSA (EX200) competence — essential tools, "
    "running systems, local storage, file systems, users/groups, security. "
    "Use the sibling rhcsa-simulator project to drill those."
)
