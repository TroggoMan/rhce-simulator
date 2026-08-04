"""
Domain 3/7: basic playbook authoring using the everyday modules —
packages, services, firewall — plus the shell-script conversion task
that is called out in the RHEL 10 objectives.
"""

import random

from core.registry import TaskRegistry
from tasks.base import AnsibleTask
from validators import ansible_runner as runner


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


@TaskRegistry.register("playbook_basics")
class CustomPortWebServerTask(AnsibleTask):
    """httpd on a non-default port: Listen + firewalld + whatever else the
    node's security policy demands. The exam's favourite composite task."""

    def __init__(self):
        super().__init__("pb_custom_port_001", "playbook_basics", "hard")

    def generate(self, **params):
        port = params.get("port") or random.choice([8080, 8404, 8888, 9090])
        text = params.get("text") or "Served on a custom port"
        self.params = {"port": port, "text": text}
        self.description = f"""
Create a playbook  custom_port.yml  in your working directory
({self.workdir}) that makes ALL managed nodes serve web content on the
NON-DEFAULT port  {port}  — and actually serve it, not just be configured
for it:

  * install httpd and have it running and enabled at boot
  * make httpd listen on port {port}
  * deploy  /var/www/html/index.html  containing:
        {text}
  * open port {port}/tcp in firewalld, both immediately and permanently
  * make sure  curl http://localhost:{port}/  on a node returns that content

That last requirement is the real test. A node's security policy may block
a service from binding a port it doesn't normally own — if so, it is part
of this task to fix that too.

Idempotent.
"""
        self.hints = [
            "lineinfile on /etc/httpd/conf/httpd.conf, regexp: '^Listen ', "
            "line: 'Listen {}'.".format(port),
            "ansible.posix.firewalld with port: '{}/tcp', permanent: true "
            "AND immediate: true (permanent alone won't apply until "
            "reload).".format(port),
            "If httpd refuses to start on a node running SELinux, the port "
            "needs the http_port_t label — community.general.seport.",
            "Restart httpd via a handler after changing the config, or it "
            "keeps listening on the old port.",
        ]
        self.exam_tips = [
            "'Configured correctly' and 'actually works' are different "
            "things, and the exam grades the second. Always curl the port "
            "yourself before moving on.",
        ]
        return self

    def validate(self):
        res = self.result()
        port = self.params["port"]
        self.check_contains(res, "custom_port.yml", rf"\b{port}\b",
                            f"playbook references port {port}")
        self.check_contains(res, "custom_port.yml",
                            r"firewalld\s*:|ansible\.posix\.firewalld",
                            "playbook uses the firewalld module")
        self.check_contains(res, "custom_port.yml", r"permanent:\s*(true|yes)",
                            "firewall rule is permanent")
        if not self.check_playbook_runs(res, "custom_port.yml"):
            return res
        self.check_node_state(res, "httpd is active", "all",
                              "ansible.builtin.command",
                              "systemctl is-active httpd", expect=r"\bactive\b",
                              become=True)
        self.check_node_state(res, "httpd is enabled at boot", "all",
                              "ansible.builtin.command",
                              "systemctl is-enabled httpd", expect=r"\benabled\b",
                              become=True)
        self.check_node_state(res, f"firewalld allows {port}/tcp", "all",
                              "ansible.builtin.command",
                              "firewall-cmd --list-ports",
                              expect=rf"{port}/tcp", become=True)
        self.check_node_state(res, f"nodes actually serve content on {port}",
                              "all", "ansible.builtin.command",
                              f"curl -sS --fail http://localhost:{port}/",
                              expect=self.params["text"], become=True)
        return res


@TaskRegistry.register("playbook_basics")
class MultiPlayPlaybookTask(AnsibleTask):
    """One playbook FILE, two independent PLAYS targeting different
    groups — the structural fundamental every other single-play task
    in this catalog skips over."""

    def __init__(self):
        super().__init__("pb_multiplay_001", "playbook_basics", "medium")

    def generate(self, **params):
        self.params = {"dev_marker": "/etc/motd.d/dev_notice",
                       "prod_marker": "/etc/motd.d/prod_notice"}
        self.description = f"""
Create a SINGLE playbook file  multiplay.yml  in your working directory
({self.workdir}) containing TWO separate plays (two top-level  - name: ...
hosts: ...  entries in one YAML file, NOT two files):

  * PLAY 1 targets the  dev   group only, and creates
    {self.params['dev_marker']}  with the content  dev environment
  * PLAY 2 targets the  prod  group only, and creates
    {self.params['prod_marker']}  with the content  prod environment

Running the ONE file must configure both groups correctly, each play
touching only its own group. Idempotent.
"""
        self.hints = [
            "A playbook file is a YAML LIST of plays — two '- name: ... "
            "hosts: ...' blocks at the top level, each with its own tasks:.",
            "This is different from one play with two host groups and a "
            "when: — here the exam specifically wants two independent "
            "plays.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "multiplay.yml", r"hosts:\s*dev\b",
                            "one play targets the dev group")
        self.check_contains(res, "multiplay.yml", r"hosts:\s*prod\b",
                            "a second play targets the prod group")
        if not self.check_playbook_runs(res, "multiplay.yml"):
            return res
        self.check_node_state(res, f"dev hosts have {self.params['dev_marker']}",
                              "dev", "ansible.builtin.command",
                              f"cat {self.params['dev_marker']}",
                              expect=r"dev environment", become=True)
        self.check_node_state(res, f"prod hosts have {self.params['prod_marker']}",
                              "prod", "ansible.builtin.command",
                              f"cat {self.params['prod_marker']}",
                              expect=r"prod environment", become=True)
        return res


@TaskRegistry.register("playbook_basics")
class TagsTask(AnsibleTask):
    """Tags — selectively running (or skipping) part of a playbook,
    graded by actually invoking --tags and confirming ONLY that part ran."""

    def __init__(self):
        super().__init__("pb_tags_001", "playbook_basics", "medium")

    def generate(self, **params):
        self.params = {
            "pkg_marker": "/var/tmp/tags_packages_ran",
            "config_marker": "/var/tmp/tags_config_ran",
        }
        self.description = f"""
Create a playbook  tags.yml  in your working directory ({self.workdir})
for ALL managed nodes with (at least) two tasks:

  * one task tagged  packages  that creates  {self.params['pkg_marker']}
  * one task tagged  config    that creates  {self.params['config_marker']}

Both tasks run on a normal, full invocation. But when run with
  ansible-playbook tags.yml --tags config
ONLY the config task may execute — the packages task must be skipped.
"""
        self.hints = [
            "tags: packages / tags: config on the respective tasks.",
            "ansible-playbook tags.yml --tags config  runs only "
            "tag-matched tasks (plus any tagged always:).",
            "--list-tags shows every tag defined in a playbook without "
            "running anything — useful for checking your own work.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "tags.yml", r"tags:\s*.*packages",
                            "a task is tagged 'packages'")
        self.check_contains(res, "tags.yml", r"tags:\s*.*config",
                            "a task is tagged 'config'")
        # A full run must complete before the selective run means anything.
        if not self.check_playbook_runs(res, "tags.yml",
                                        require_idempotent=False):
            return res
        if not runner.have_ansible():
            return res
        # Clear both markers, then re-run with --tags config only.
        self.probe("ansible.builtin.command",
                  f"rm -f {self.params['pkg_marker']} {self.params['config_marker']}",
                  become=True)
        outcome = runner.full_playbook_check(
            self.workdir / "tags.yml", self.workdir,
            extra_args=["--tags", "config"])
        res.add("selective run (--tags config) executes cleanly", outcome.run_ok,
                "" if outcome.run_ok else outcome.detail)
        self.check_node_state(res, f"{self.params['config_marker']} was created",
                              "all", "ansible.builtin.command",
                              f"test -e {self.params['config_marker']}", become=True)
        self.check_node_state(res, f"{self.params['pkg_marker']} was NOT created "
                              "(tag correctly excluded it)",
                              "all", "ansible.builtin.shell",
                              f"test -e {self.params['pkg_marker']} && echo RAN || echo SKIPPED",
                              expect=r"SKIPPED", become=True)
        return res
