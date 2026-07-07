"""
Domain 3/7: basic playbook authoring using the everyday modules —
packages, services, firewall — plus the shell-script conversion task
that is called out in the RHEL 10 objectives.
"""

import random

from core.registry import TaskRegistry
from tasks.base import AnsibleTask


@TaskRegistry.register("playbook_basics")
class PackagesPlaybookTask(AnsibleTask):
    def __init__(self):
        super().__init__("pb_packages_001", "playbook_basics", "easy")

    def generate(self, **params):
        pkgs = params.get("pkgs") or random.choice(
            [["httpd", "mod_ssl"], ["mariadb-server", "mariadb"],
             ["vsftpd", "tar"], ["samba", "samba-client"]])
        self.params = {"pkgs": pkgs}
        pkg_lines = "\n".join(f"      - {p}" for p in pkgs)
        self.description = f"""
Create a playbook  packages.yml  in your working directory ({self.workdir})
that installs the following packages on ALL managed nodes:

{pkg_lines}

The playbook must be idempotent (a second run reports changed=0).
"""
        self.hints = [
            "ansible.builtin.dnf with a list under name: (one task, not one per package).",
            "state: present is idempotent; state: latest usually is not.",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_playbook_runs(res, "packages.yml"):
            return res
        for pkg in self.params["pkgs"]:
            self.check_node_state(res, f"package {pkg} installed on all nodes",
                                  "all", "ansible.builtin.command",
                                  f"rpm -q {pkg}", expect=rf"{pkg}-\d")
        return res


@TaskRegistry.register("playbook_basics")
class WebServerPlaybookTask(AnsibleTask):
    def __init__(self):
        super().__init__("pb_webserver_001", "playbook_basics", "medium")

    def generate(self, **params):
        self.params = {"svc": "httpd", "fw_svc": "http"}
        self.description = f"""
Create a playbook  webserver.yml  in your working directory ({self.workdir})
that configures ALL managed nodes as web servers:

  * install  httpd
  * start it and enable it at boot
  * open the  http  service permanently in firewalld (runtime and permanent)

The playbook must be idempotent.
"""
        self.hints = [
            "Three tasks: dnf, service (enabled: true, state: started), firewalld.",
            "firewalld module lives in ansible.posix; permanent: true AND immediate: true.",
            "If firewalld isn't running on a node, the firewalld task needs it up first.",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_playbook_runs(res, "webserver.yml"):
            return res
        self.check_node_state(res, "httpd is active on all nodes",
                              "all", "ansible.builtin.command",
                              "systemctl is-active httpd", expect=r"\bactive\b",
                              become=True)
        self.check_node_state(res, "httpd is enabled on all nodes",
                              "all", "ansible.builtin.command",
                              "systemctl is-enabled httpd", expect=r"\benabled\b",
                              become=True)
        self.check_node_state(res, "http allowed in firewalld",
                              "all", "ansible.builtin.command",
                              "firewall-cmd --list-services", expect=r"\bhttp\b",
                              become=True)
        return res


@TaskRegistry.register("playbook_basics")
class ScriptToPlaybookTask(AnsibleTask):
    """RHEL 10 objective: analyze simple shell scripts and convert them."""

    def __init__(self):
        super().__init__("pb_script_convert_001", "playbook_basics", "medium")

    def generate(self, **params):
        directory = params.get("dir") or random.choice(
            ["/opt/app_data", "/srv/deploy", "/opt/webcontent"])
        pkg = params.get("pkg") or random.choice(["tree", "rsync", "bash-completion"])
        self.params = {"dir": directory, "pkg": pkg}
        self.description = f"""
An admin left behind this shell script that used to be run by hand on
every server:

    #!/bin/bash
    dnf install -y {pkg}
    mkdir -p {directory}
    chmod 0755 {directory}
    echo "prepared $(hostname)" > {directory}/ready.txt

Convert it to an equivalent, idempotent playbook  convert.yml  in your
working directory ({self.workdir}) that runs against ALL managed nodes.
Use proper Ansible modules — no shell/command tasks — and use an Ansible
fact instead of $(hostname).
"""
        self.hints = [
            "dnf, file (state: directory, mode:), copy (content:).",
            "The hostname fact is {{ ansible_facts['hostname'] }}.",
            "shell/command tasks are almost never idempotent — graders re-run playbooks.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "convert.yml", r"ansible_facts|ansible_hostname|ansible_fqdn",
                            "playbook uses a fact for the hostname")
        bad_shell = self.workdir.joinpath("convert.yml").exists() and \
            not self._uses_shell()
        res.add("no shell/command modules used", bad_shell,
                "" if bad_shell else "replace shell/command tasks with real modules")
        if not self.check_playbook_runs(res, "convert.yml"):
            return res
        self.check_node_state(res, f"{self.params['dir']}/ready.txt exists with hostname",
                              "all", "ansible.builtin.command",
                              f"cat {self.params['dir']}/ready.txt",
                              expect=r"prepared \S+", become=True)
        return res

    def _uses_shell(self) -> bool:
        try:
            text = (self.workdir / "convert.yml").read_text()
        except OSError:
            return True
        import re
        return re.search(r"(ansible\.builtin\.)?(shell|command)\s*:", text) is not None
