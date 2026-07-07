"""Domain 5: creating roles, installing roles, RHEL system roles."""

import random

from core.registry import TaskRegistry
from tasks.base import AnsibleTask


@TaskRegistry.register("roles")
class CreateRoleTask(AnsibleTask):
    def __init__(self):
        super().__init__("role_create_001", "roles", "hard")

    def generate(self, **params):
        role = params.get("role") or random.choice(["apache_dev", "web_role", "sample_apache"])
        self.params = {"role": role}
        self.description = f"""
In your working directory ({self.workdir}), create a role  {role}
under  roles/  that:

  * installs and starts httpd
  * deploys /var/www/html/index.html from a template in the role, with
    the content:   Welcome to <fqdn>

Then create a playbook  role_play.yml  that applies the role to ALL
managed nodes. Idempotent.
"""
        self.hints = [
            "ansible-galaxy role init roles/" + role,
            "Role structure: tasks/main.yml, templates/, handlers/main.yml.",
            "In role templates you reference facts exactly like in playbooks.",
        ]
        return self

    def validate(self):
        res = self.result()
        role = self.params["role"]
        if not self.check_exists(res, f"roles/{role}/tasks/main.yml"):
            return res
        self.check_contains(res, "role_play.yml", rf"roles:[\s\S]{{0,120}}{role}",
                            "playbook applies the role")
        if not self.check_playbook_runs(res, "role_play.yml"):
            return res
        self.check_node_state(res, "index.html rendered with node fqdn",
                              "all", "ansible.builtin.command",
                              "cat /var/www/html/index.html",
                              expect=r"Welcome to \S+", become=True)
        self.check_node_state(res, "httpd is active", "all",
                              "ansible.builtin.command",
                              "systemctl is-active httpd", expect=r"\bactive\b",
                              become=True)
        return res


@TaskRegistry.register("roles")
class RequirementsRoleTask(AnsibleTask):
    def __init__(self):
        super().__init__("role_requirements_001", "roles", "medium")

    def generate(self, **params):
        self.description = f"""
Create a requirements file  roles/requirements.yml  in your working
directory ({self.workdir}) that installs two roles from external sources
(on the real exam the URLs are given; here pick any two, e.g. from
galaxy.ansible.com or a git URL):

  * one role fetched by galaxy name, installed AS the name  balancer
  * one role fetched from a URL (src:), installed AS the name  phphello

Then install them into  roles/  with ansible-galaxy.
"""
        self.hints = [
            "Entries: - src: <name-or-url>, name: <install-as>.",
            "ansible-galaxy role install -r roles/requirements.yml -p roles",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_exists(res, "roles/requirements.yml"):
            return res
        self.check_contains(res, "roles/requirements.yml", r"src:",
                            "requirements file defines role sources")
        self.check_contains(res, "roles/requirements.yml",
                            r"name:\s*balancer", "role installed as 'balancer'")
        self.check_contains(res, "roles/requirements.yml",
                            r"name:\s*phphello", "role installed as 'phphello'")
        installed = (self.workdir / "roles/balancer").is_dir() and \
                    (self.workdir / "roles/phphello").is_dir()
        res.add("both roles installed under roles/", installed,
                "" if installed else
                "run: ansible-galaxy role install -r roles/requirements.yml -p roles")
        return res


@TaskRegistry.register("system_roles")
class TimesyncSystemRoleTask(AnsibleTask):
    def __init__(self):
        super().__init__("sysrole_timesync_001", "system_roles", "medium")

    def generate(self, **params):
        server = params.get("server") or random.choice(
            ["0.rhel.pool.ntp.org", "1.rhel.pool.ntp.org", "time.cloudflare.com"])
        self.params = {"server": server}
        self.description = f"""
Use the RHEL  timesync  system role. In your working directory
({self.workdir}) create a playbook  timesync.yml  that runs on ALL
managed nodes and configures time synchronization to use the NTP server:

    {server}      (iburst enabled)

Install the system roles first if needed
(dnf install rhel-system-roles  — or
 ansible-galaxy collection install redhat.rhel_system_roles).
"""
        self.hints = [
            "Role name: rhel-system-roles.timesync (RPM) or redhat.rhel_system_roles.timesync (collection).",
            "Variable: timesync_ntp_servers: [{hostname: …, iburst: true}]",
            "System roles docs live in /usr/share/doc/rhel-system-roles/.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "timesync.yml",
                            r"(rhel[-_]system[-_]roles\.|linux[-_]system[-_]roles\.)?timesync",
                            "playbook uses the timesync system role")
        self.check_contains(res, "timesync.yml", r"timesync_ntp_servers",
                            "NTP servers set via role variable")
        self.check_contains(res, "timesync.yml", self.params["server"].replace(".", r"\."),
                            "required NTP server configured")
        self.check_playbook_runs(res, "timesync.yml")
        return res


@TaskRegistry.register("collections")
class CollectionInstallTask(AnsibleTask):
    def __init__(self):
        super().__init__("coll_install_001", "collections", "easy")

    def generate(self, **params):
        self.params = {"collections": ["ansible.posix", "community.general"]}
        self.description = f"""
In your working directory ({self.workdir}):

  1. Create  collections/requirements.yml  listing these collections:
        ansible.posix
        community.general
  2. Install them INTO the  ./collections  directory (not the default
     user location):
        ansible-galaxy collection install -r collections/requirements.yml -p collections
  3. Make sure Ansible finds them there (collections_path in ansible.cfg).
"""
        self.hints = [
            "requirements.yml: top-level 'collections:' list.",
            "ansible.cfg: collections_path = ./collections (under [defaults]).",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_exists(res, "collections/requirements.yml"):
            return res
        for coll in self.params["collections"]:
            self.check_contains(res, "collections/requirements.yml",
                                coll.replace(".", r"\."),
                                f"requirements lists {coll}")
            path = self.workdir / "collections/ansible_collections" / coll.replace(".", "/")
            res.add(f"{coll} installed under ./collections", path.is_dir(),
                    "" if path.is_dir() else
                    "ansible-galaxy collection install -r collections/requirements.yml -p collections")
        return res
