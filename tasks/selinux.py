"""
Domain 10: SELinux automation — modes, booleans, ports and file contexts.

The objective bullet is "security (SELinux modes, booleans, file contexts)",
and the classic exam pairing is "serve content from a non-default port or a
non-default directory", which fails silently until BOTH the firewall and the
SELinux label are right.

Deployment note: every task here grades its artifact layer unconditionally,
then probes for a live SELinux subsystem before running anything. In the
Docker lab there isn't one (containers share the host kernel and get no
selinuxfs), so execution and node-state checks are recorded as SKIPPED with
an explanation rather than failed — a correct playbook is never scored as
wrong just because the lab can't observe it. Point RHCE_SIM_NODES at a
RHEL/Rocky/Alma 10 VM to grade these end to end.

Collection trap worth knowing cold: these modules are split across two
collections. seboolean and selinux are ansible.posix; seport and sefcontext
are community.general.
"""

import random

from core.registry import TaskRegistry
from tasks.base import AnsibleTask


@TaskRegistry.register("selinux")
class SelinuxModeTask(AnsibleTask):
    """SELinux modes — the 'modes' third of the objective bullet."""

    def __init__(self):
        super().__init__("sel_mode_001", "selinux", "easy")

    def generate(self, **params):
        self.params = {"policy": "targeted", "state": "enforcing"}
        self.description = f"""
Create a playbook  selinux_mode.yml  in your working directory
({self.workdir}) that, on ALL managed nodes, ensures SELinux is:

  * running the  targeted  policy
  * in  enforcing  mode
  * and that this survives a reboot (persistent, not just runtime)

Idempotent.
"""
        self.hints = [
            "ansible.posix.selinux (NOT community.general) with policy: and state:.",
            "state: enforcing here means the persistent config, not just setenforce 1.",
            "The module can report 'reboot required' — that's a normal return "
            "value when moving out of disabled, not a failure.",
        ]
        self.exam_tips = [
            "Going from disabled to enforcing needs a reboot and a full "
            "filesystem relabel — moving between permissive and enforcing "
            "does not. Know which transition you're being asked for.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "selinux_mode.yml",
                            r"(ansible\.posix\.)?selinux\s*:",
                            "playbook uses the selinux module")
        self.check_contains(res, "selinux_mode.yml", r"state:\s*enforcing",
                            "enforcing mode requested")
        self.check_contains(res, "selinux_mode.yml", r"policy:\s*targeted",
                            "targeted policy requested")
        if self.skip_without_selinux(res, "selinux_mode.yml runs and nodes end up enforcing"):
            return res
        if not self.check_playbook_runs(res, "selinux_mode.yml"):
            return res
        self.check_node_state(res, "nodes report Enforcing", "all",
                              "ansible.builtin.command", "getenforce",
                              expect=r"Enforcing", become=True)
        return res


@TaskRegistry.register("selinux")
class SeBooleanTask(AnsibleTask):
    """SELinux booleans — persistently flipping policy switches."""

    def __init__(self):
        super().__init__("sel_boolean_001", "selinux", "medium")

    def generate(self, **params):
        boolean = params.get("boolean") or random.choice([
            "httpd_can_network_connect",
            "httpd_enable_homedirs",
            "ftpd_full_access",
        ])
        self.params = {"boolean": boolean}
        self.description = f"""
Create a playbook  seboolean.yml  in your working directory ({self.workdir})
that, on ALL managed nodes, turns the SELinux boolean

    {boolean}

ON, and makes the change PERSISTENT across reboots.

Idempotent — a second run must report changed=0.
"""
        self.hints = [
            "ansible.posix.seboolean with name:, state: true, persistent: true.",
            "Without persistent: true the boolean reverts on the next reboot — "
            "and every Red Hat exam requires config to survive a reboot.",
            "List booleans on a node with: getsebool -a | grep httpd",
        ]
        self.exam_tips = [
            "Forgetting persistent: true is the single most common way to "
            "lose points on a boolean task — it looks correct right up until "
            "the grader reboots the node.",
        ]
        return self

    def validate(self):
        res = self.result()
        boolean = self.params["boolean"]
        self.check_contains(res, "seboolean.yml",
                            r"(ansible\.posix\.)?seboolean\s*:",
                            "playbook uses the seboolean module")
        self.check_contains(res, "seboolean.yml", boolean,
                            f"playbook targets the {boolean} boolean")
        self.check_contains(res, "seboolean.yml", r"persistent:\s*(true|yes)",
                            "boolean change is persistent")
        if self.skip_without_selinux(res, "seboolean.yml runs and the boolean is on"):
            return res
        if not self.check_playbook_runs(res, "seboolean.yml"):
            return res
        self.check_node_state(res, f"{boolean} is on across all nodes", "all",
                              "ansible.builtin.command", f"getsebool {boolean}",
                              expect=r"-->\s*on", become=True)
        return res


@TaskRegistry.register("selinux")
class SePortTask(AnsibleTask):
    """Port labelling — the half of 'httpd on a custom port' people forget."""

    def __init__(self):
        super().__init__("sel_port_001", "selinux", "medium")

    def generate(self, **params):
        port = params.get("port") or random.choice([8080, 8404, 8888, 9090])
        self.params = {"port": port, "setype": "http_port_t"}
        self.description = f"""
Apache needs to listen on a non-default port. SELinux will block that until
the port itself carries the right label.

Create a playbook  seport.yml  in your working directory ({self.workdir})
that, on ALL managed nodes, adds TCP port  {port}  to the SELinux port type

    http_port_t

Make sure the managed nodes have the tooling the module needs, and keep the
playbook idempotent.
"""
        self.hints = [
            "community.general.seport (NOT ansible.posix) with ports:, "
            "proto: tcp, setype: http_port_t, state: present.",
            "The module shells out to semanage — install "
            "policycoreutils-python-utils on the nodes first.",
            "Check the result with: semanage port -l | grep http_port_t",
        ]
        self.exam_tips = [
            "A custom web port needs THREE things, and partial credit is not "
            "given for two of them: the Listen directive, the firewalld rule, "
            "and this SELinux port label.",
        ]
        return self

    def validate(self):
        res = self.result()
        port = self.params["port"]
        self.check_contains(res, "seport.yml",
                            r"(community\.general\.)?seport\s*:",
                            "playbook uses the seport module")
        self.check_contains(res, "seport.yml", rf"\b{port}\b",
                            f"playbook labels port {port}")
        self.check_contains(res, "seport.yml", r"http_port_t",
                            "port is added to http_port_t")
        self.check_contains(res, "seport.yml",
                            r"policycoreutils-python-utils|python3-libsemanage",
                            "playbook installs the semanage tooling it needs")
        if self.skip_without_selinux(res, "seport.yml runs and the port is labelled"):
            return res
        if not self.check_playbook_runs(res, "seport.yml"):
            return res
        self.check_node_state(res, f"port {port} carries http_port_t", "all",
                              "ansible.builtin.shell",
                              "semanage port -l | grep http_port_t",
                              expect=rf"\b{port}\b", become=True)
        return res


@TaskRegistry.register("selinux")
class SeFcontextTask(AnsibleTask):
    """File contexts — a rule plus the relabel that actually applies it."""

    def __init__(self):
        super().__init__("sel_fcontext_001", "selinux", "hard")

    def generate(self, **params):
        docroot = params.get("docroot") or random.choice(
            ["/srv/www", "/opt/webroot", "/data/website"])
        self.params = {"docroot": docroot, "setype": "httpd_sys_content_t"}
        self.description = f"""
A web server is being moved out of /var/www onto its own directory, which
SELinux will deny access to until the directory is labelled correctly.

Create a playbook  sefcontext.yml  in your working directory ({self.workdir})
that, on ALL managed nodes:

  1. creates the directory  {docroot}
  2. adds a PERSISTENT file-context rule labelling {docroot} and everything
     beneath it as  httpd_sys_content_t
  3. APPLIES that rule to the files already on disk

Step 3 is not optional: adding a context rule changes the policy database,
it does not relabel anything that already exists.

Idempotent.
"""
        self.hints = [
            "community.general.sefcontext with target: '{}(/.*)?', "
            "setype: httpd_sys_content_t, state: present.".format(docroot),
            "The (/.*)? suffix is a regex meaning 'this directory and "
            "everything under it' — without it you label only the directory.",
            "Apply it with ansible.builtin.command: restorecon -Rv <dir> "
            "(the sefcontext module deliberately does not relabel for you).",
        ]
        self.exam_tips = [
            "sefcontext writes the RULE; restorecon APPLIES it. A playbook "
            "with only the first half looks right, passes a syntax check, "
            "and still leaves the web server getting permission denied.",
        ]
        return self

    def validate(self):
        res = self.result()
        docroot = self.params["docroot"]
        self.check_contains(res, "sefcontext.yml",
                            r"(community\.general\.)?sefcontext\s*:",
                            "playbook uses the sefcontext module")
        self.check_contains(res, "sefcontext.yml", r"httpd_sys_content_t",
                            "rule sets httpd_sys_content_t")
        self.check_contains(res, "sefcontext.yml", r"\(/\.\*\)\?",
                            "rule covers the directory recursively — (/.*)?")
        self.check_contains(res, "sefcontext.yml", r"restorecon",
                            "playbook relabels existing files with restorecon")
        if self.skip_without_selinux(res, "sefcontext.yml runs and files are relabelled"):
            return res
        if not self.check_playbook_runs(res, "sefcontext.yml"):
            return res
        self.check_node_state(res, f"{docroot} is labelled httpd_sys_content_t",
                              "all", "ansible.builtin.command",
                              f"ls -Zd {docroot}",
                              expect=r"httpd_sys_content_t", become=True)
        return res
