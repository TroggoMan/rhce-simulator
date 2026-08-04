"""Domain 5: creating roles, installing roles, RHEL system roles."""

import random
import re

from config import settings
from core.registry import TaskRegistry
from tasks.base import AnsibleTask
from tasks.storage import NO_SPARE_DISK


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


# Only NetworkManager can drive the network role's dummy interfaces, and the
# Docker lab has no NetworkManager at all — so probe before running anything
# rather than failing a correct playbook.
NO_NETWORKMANAGER = (
    "These managed nodes aren't running NetworkManager, which the network "
    "system role requires (it is the only supported provider for dummy "
    "interfaces), so the playbook wasn't run — your file was still graded "
    "on content above.\n"
    "The Docker lab doesn't ship NetworkManager; point RHCE_SIM_NODES at a "
    "RHEL/Rocky/Alma 10 VM to grade this end to end."
)


@TaskRegistry.register("system_roles")
class NetworkSystemRoleTask(AnsibleTask):
    """Static addressing via the network system role.

    Deliberately targets a throwaway DUMMY interface using TEST-NET-1
    (RFC 5737) addresses: a candidate's playbook can therefore never
    reconfigure — or cut off — the real interface Ansible is connected over.
    """

    def __init__(self):
        super().__init__("sysrole_network_001", "system_roles", "hard")

    def generate(self, **params):
        iface = "ex294dummy"
        self.params = {
            "iface": iface,
            "address": "192.0.2.10/24",
            "gateway": "192.0.2.1",
            "dns": "192.0.2.53",
        }
        self.description = f"""
Use the RHEL  network  system role to configure a secondary interface with
static addressing. In your working directory ({self.workdir}) create a
playbook  network_role.yml  that runs on ALL managed nodes and configures
a DUMMY interface named  {iface}  with:

  * static IPv4 address:  {self.params['address']}
  * gateway:              {self.params['gateway']}
  * DNS server:           {self.params['dns']}
  * DHCP explicitly DISABLED
  * the connection brought up, and persistent across reboots

Apply the role with  include_role  or  import_role , and define the
interface through the role's  network_connections  variable.

(These are TEST-NET-1 addresses on a dummy interface — nothing here can
disturb the connection Ansible is using to reach the node.)
"""
        self.hints = [
            "Role name: redhat.rhel_system_roles.network (collection) or "
            "rhel-system-roles.network (RPM). Install with: dnf install "
            "rhel-system-roles.",
            "network_connections is a LIST of connection dictionaries: "
            "name, type, interface_name, ip, state.",
            "type: dummy — and the ip dict takes address (a LIST), gateway4, "
            "dns (a LIST), dhcp4: false.",
            "state: up brings the connection online; persistence comes from "
            "the role writing a real connection profile.",
        ]
        self.exam_tips = [
            "ip.address and ip.dns are lists even when you only have one "
            "value — passing a bare string is the usual reason the role "
            "errors out with a confusing schema message.",
            "RHEL 10 ships the rhel-system-roles RPM in its AppStream "
            "repository, and the roles are referenced as "
            "redhat.rhel_system_roles.<role>. fedora.linux_system_roles is "
            "the upstream project — same roles, different namespace. "
            "Practise with the redhat. namespace so you're not reaching for "
            "content the exam image doesn't have.",
        ]
        return self

    def validate(self):
        res = self.result()
        p = self.params
        self.check_contains(res, "network_role.yml",
                            r"(rhel[-_]system[-_]roles|linux[-_]system[-_]roles)?\.?network\b",
                            "playbook applies the network system role")
        self.check_contains(res, "network_role.yml",
                            r"include_role|import_role|roles:",
                            "role applied via include_role/import_role")
        self.check_contains(res, "network_role.yml", r"network_connections",
                            "interface defined via network_connections")
        self.check_contains(res, "network_role.yml", p["iface"],
                            f"playbook configures {p['iface']}")
        self.check_contains(res, "network_role.yml",
                            p["address"].replace(".", r"\.").replace("/", "/"),
                            "required static address present")
        self.check_contains(res, "network_role.yml", r"dhcp4:\s*(false|no)",
                            "DHCP explicitly disabled")
        # NetworkManager is mandatory for this role's dummy support.
        if not self.probe("ansible.builtin.command",
                          "systemctl is-active NetworkManager",
                          expect=r"\bactive\b", become=True):
            res.add_skip("network_role.yml runs and the interface is configured",
                         NO_NETWORKMANAGER)
            return res
        if not self.check_playbook_runs(res, "network_role.yml"):
            return res
        self.check_node_state(res, f"{p['iface']} carries {p['address']}",
                              "all", "ansible.builtin.command",
                              f"ip -4 addr show {p['iface']}",
                              expect=p["address"].replace(".", r"\."),
                              become=True)
        return res


@TaskRegistry.register("roles")
class RoleVariablesOverrideTask(AnsibleTask):
    """defaults/ vs vars/ vs playbook-level overrides — the precedence
    chain every role author (and every candidate reading one) needs cold."""

    def __init__(self):
        super().__init__("role_vars_override_001", "roles", "medium")

    def generate(self, **params):
        pkg = params.get("pkg") or random.choice(["tree", "rsync", "htop"])
        self.params = {"role": "content_role", "default_pkg": "tar", "pkg": pkg}
        self.description = f"""
Roles ship sensible defaults that callers can override. In your working
directory ({self.workdir}):

  1. Create a role  {self.params['role']}  under  roles/  whose
     tasks/main.yml installs a package named by the variable  target_pkg .
  2. In  roles/{self.params['role']}/defaults/main.yml , set
        target_pkg: {self.params['default_pkg']}
  3. Create a playbook  role_override.yml  that applies the role to ALL
     managed nodes, overriding  target_pkg  to  {pkg}  at the PLAY level
     (vars: on the play, not inside the role).

The node state must show  {pkg}  installed — proving your override beat
the role's default — and  {self.params['default_pkg']}  must NOT have been
installed by this playbook.

Idempotent.
"""
        self.hints = [
            "defaults/main.yml has the LOWEST precedence — play vars: "
            "always beats it, which is exactly what makes defaults safe to "
            "ship.",
            "Role tasks reference the variable the same way regardless of "
            "where it ultimately comes from: {{ target_pkg }}.",
            "vars: at the play level (a sibling of hosts: and roles:), not "
            "vars_files or role vars/, is what's graded here.",
        ]
        return self

    def validate(self):
        res = self.result()
        role = self.params["role"]
        if not self.check_exists(res, f"roles/{role}/defaults/main.yml"):
            return res
        self.check_contains(res, f"roles/{role}/defaults/main.yml",
                            rf"target_pkg:\s*{self.params['default_pkg']}",
                            "role ships a default for target_pkg")
        self.check_contains(res, "role_override.yml",
                            rf"target_pkg:\s*{self.params['pkg']}",
                            "playbook overrides target_pkg at the play level")
        if not self.check_playbook_runs(res, "role_override.yml"):
            return res
        self.check_node_state(res, f"{self.params['pkg']} installed (override won)",
                              "all", "ansible.builtin.command",
                              f"rpm -q {self.params['pkg']}",
                              expect=rf"{self.params['pkg']}-\d", become=True)
        return res


@TaskRegistry.register("roles")
class RoleMetaDependencyTask(AnsibleTask):
    """Role dependencies declared in meta/main.yml run automatically —
    applying ONE role in the playbook is the whole point of the test."""

    def __init__(self):
        super().__init__("role_meta_dep_001", "roles", "hard")

    def generate(self, **params):
        self.params = {"base": "base_setup", "top": "app_deploy",
                       "marker": "/var/tmp/base_setup_ran"}
        self.description = f"""
In your working directory ({self.workdir}), create TWO roles under  roles/ :

  1.  {self.params['base']}  — its tasks/main.yml creates the file
      {self.params['marker']}  (any content).
  2.  {self.params['top']}  — its  meta/main.yml  declares a DEPENDENCY on
      {self.params['base']} , and its own tasks/main.yml installs the
      package  tree .

Create a playbook  role_deps.yml  that applies ONLY  {self.params['top']}
to ALL managed nodes (do not list {self.params['base']} in the playbook
directly — the dependency mechanism must be what runs it).

After running, both the marker file AND the tree package must be present
on every node, even though the playbook only names one role.
"""
        self.hints = [
            "meta/main.yml: dependencies: - role: " + self.params["base"],
            "Ansible runs a role's dependencies BEFORE the role's own tasks, "
            "automatically, once per play — no include_role needed.",
            "ansible-galaxy role init roles/<name> scaffolds meta/main.yml "
            "for you.",
        ]
        self.exam_tips = [
            "Listing a dependency in meta/main.yml is different from "
            "listing two roles in the playbook's roles: — the exam "
            "sometimes explicitly asks for the dependency form to test "
            "whether you know it exists.",
        ]
        return self

    def validate(self):
        res = self.result()
        base, top = self.params["base"], self.params["top"]
        if not self.check_exists(res, f"roles/{top}/meta/main.yml"):
            return res
        self.check_contains(res, f"roles/{top}/meta/main.yml",
                            rf"role:\s*{base}", f"{top} declares a dependency on {base}")
        self.check_contains(res, "role_deps.yml", rf"roles:[\s\S]{{0,80}}{top}",
                            f"playbook applies {top}")
        playbook_path = self.workdir / "role_deps.yml"
        try:
            playbook_text = playbook_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            playbook_text = ""
        no_direct = base not in playbook_text
        res.add(f"playbook does not list {base} directly", no_direct,
                "" if no_direct else f"remove {base} from role_deps.yml — it "
                "should run only via the dependency")
        if not self.check_playbook_runs(res, "role_deps.yml"):
            return res
        self.check_node_state(res, f"{self.params['marker']} exists (dependency ran)",
                              "all", "ansible.builtin.command",
                              f"test -e {self.params['marker']}", become=True)
        self.check_node_state(res, "tree installed (top-level role ran)",
                              "all", "ansible.builtin.command",
                              "rpm -q tree", expect=r"tree-\d", become=True)
        return res


@TaskRegistry.register("system_roles")
class StorageSystemRoleTask(AnsibleTask):
    """The storage system role vs. hand-rolled parted/lvg/lvol/filesystem —
    same end state, a completely different (and much shorter) playbook."""

    def __init__(self):
        super().__init__("sysrole_storage_001", "system_roles", "hard")

    def generate(self, **params):
        device = params.get("device") or settings.get_spare_disk()
        mount = params.get("mount") or "/srv/rolestorage"
        self.params = {"device": device, "short": device.split("/")[-1],
                       "mount": mount, "vol": "rolevol"}
        p = self.params
        self.description = f"""
Rebuild the "spare disk to mounted filesystem" chain using the RHEL
storage  SYSTEM ROLE instead of individual LVM modules — much less YAML
for the same result.

Create a playbook  storage_role.yml  in your working directory
({self.workdir}) that, ONLY on managed nodes that actually have
{device} , uses the  storage  system role (install rhel-system-roles /
ansible-galaxy collection install redhat.rhel_system_roles first if
needed) to:

  * consume the whole disk {device} as a single volume named  {p['vol']}
  * format it  ext4
  * mount it persistently at  {mount}

Nodes without {device} must be skipped cleanly, not fail.
"""
        self.hints = [
            "include_role: name: storage (or redhat.rhel_system_roles.storage) "
            "guarded by the same when: fact check as the manual LVM task.",
            "Variable: storage_volumes — a list of dicts with name:, "
            "type: disk, disks: [<device>], fs_type: ext4, mount_point:.",
            "The role handles partitioning, PV/VG/LV (if needed) AND the "
            "fstab entry in one variable block — that's the whole pitch.",
        ]
        self.exam_tips = [
            "storage_volumes' disks: takes the whole-disk device name "
            "(e.g. /dev/vdb), not a partition — the role does the "
            "partitioning/LVM layer itself when a type isn't specified as "
            "raw.",
        ]
        return self

    def validate(self):
        res = self.result()
        p = self.params
        self.check_contains(res, "storage_role.yml",
                            r"(rhel[-_]system[-_]roles|linux[-_]system[-_]roles)?\.?storage\b",
                            "playbook applies the storage system role")
        self.check_contains(res, "storage_role.yml", r"storage_volumes",
                            "volumes defined via storage_volumes")
        self.check_contains(res, "storage_role.yml", p["mount"],
                            f"playbook targets mount point {p['mount']}")
        self.check_contains(res, "storage_role.yml",
                            rf"when:[\s\S]{{0,120}}(devices|{p['short']})",
                            "acts only on hosts that have the disk (fact-based)")
        if not self.check_playbook_runs(res, "storage_role.yml"):
            return res
        if not self.probe("ansible.builtin.command",
                          f"test -b {p['device']}", become=True,
                          require_all=False):
            res.add_skip(f"{p['mount']} ends up mounted", NO_SPARE_DISK)
            return res
        guard = f"test -b {p['device']} || exit 0; "
        self.check_node_state(res, f"{p['mount']} is mounted as ext4", "all",
                              "ansible.builtin.shell",
                              guard + f"findmnt -no FSTYPE {p['mount']} | grep -q ext4",
                              become=True)
        return res


@TaskRegistry.register("system_roles")
class SelinuxSystemRoleTask(AnsibleTask):
    """The selinux system role — declarative booleans/mode instead of the
    individual seboolean/selinux modules used in the SELinux category."""

    def __init__(self):
        super().__init__("sysrole_selinux_001", "system_roles", "medium")

    def generate(self, **params):
        boolean = params.get("boolean") or random.choice(
            ["httpd_can_network_connect", "httpd_enable_homedirs"])
        self.params = {"boolean": boolean}
        self.description = f"""
Use the RHEL  selinux  system role to configure SELinux declaratively.
Create a playbook  selinux_role.yml  in your working directory
({self.workdir}) that runs on ALL managed nodes and, via the system role:

  * ensures SELinux is running the  targeted  policy in  enforcing  mode
  * turns the boolean  {boolean}  ON, persistently

Install rhel-system-roles (or the redhat.rhel_system_roles collection)
first if needed.
"""
        self.hints = [
            "include_role: name: selinux (or redhat.rhel_system_roles.selinux).",
            "Variables: selinux_policy: targeted, selinux_state: enforcing.",
            "selinux_booleans: a list of {{name: ..., state: true}} dicts — "
            "the role makes the change persistent by default.",
        ]
        self.exam_tips = [
            "The selinux role and the ansible.posix.selinux/seboolean "
            "modules configure the exact same underlying state two "
            "different ways — the exam may specify either approach by name.",
        ]
        return self

    def validate(self):
        res = self.result()
        boolean = self.params["boolean"]
        self.check_contains(res, "selinux_role.yml",
                            r"(rhel[-_]system[-_]roles|linux[-_]system[-_]roles)?\.?selinux\b",
                            "playbook applies the selinux system role")
        self.check_contains(res, "selinux_role.yml", r"selinux_policy:\s*targeted",
                            "targeted policy requested")
        self.check_contains(res, "selinux_role.yml", r"selinux_state:\s*enforcing",
                            "enforcing mode requested")
        self.check_contains(res, "selinux_role.yml", boolean,
                            f"playbook targets the {boolean} boolean")
        if self.skip_without_selinux(res, "selinux_role.yml runs and nodes end up enforcing"):
            return res
        if not self.check_playbook_runs(res, "selinux_role.yml"):
            return res
        self.check_node_state(res, "nodes report Enforcing", "all",
                              "ansible.builtin.command", "getenforce",
                              expect=r"Enforcing", become=True)
        self.check_node_state(res, f"{boolean} is on across all nodes", "all",
                              "ansible.builtin.command", f"getsebool {boolean}",
                              expect=r"-->\s*on", become=True)
        return res


@TaskRegistry.register("collections")
class CollectionModuleUsageTask(AnsibleTask):
    """Installing a collection is half the objective bullet — USING one of
    its modules in a real playbook is the other half."""

    def __init__(self):
        super().__init__("coll_usage_001", "collections", "medium")

    def generate(self, **params):
        tz = params.get("tz") or random.choice(
            ["Africa/Johannesburg", "UTC", "Europe/London"])
        self.params = {"tz": tz}
        self.description = f"""
In your working directory ({self.workdir}):

  1. Ensure the  community.general  collection is installed.
  2. Create a playbook  timezone.yml  that, using the
     community.general.timezone  module (NOT a shell command), sets the
     system timezone on ALL managed nodes to  {tz} .

Idempotent.
"""
        self.hints = [
            "ansible-galaxy collection install community.general",
            "community.general.timezone: name: " + tz,
            "Setting TZ by editing /etc/localtime by hand is exactly what "
            "this module exists to replace — using timedatectl/shell "
            "instead of the module fails this task even if the end state "
            "looks right.",
        ]
        return self

    def validate(self):
        res = self.result()
        tz = self.params["tz"]
        self.check_contains(res, "timezone.yml",
                            r"(community\.general\.)?timezone\s*:",
                            "playbook uses the timezone module")
        self.check_contains(res, "timezone.yml", re.escape(tz),
                            f"playbook sets timezone to {tz}")
        if not self.check_playbook_runs(res, "timezone.yml"):
            return res
        self.check_node_state(res, f"nodes report timezone {tz}", "all",
                              "ansible.builtin.command", "timedatectl show -p Timezone",
                              expect=re.escape(tz), become=True)
        return res


@TaskRegistry.register("collections")
class CollectionVersionPinTask(AnsibleTask):
    """Pinning a collection to a version range in requirements.yml — the
    reproducibility half of the collections objective."""

    def __init__(self):
        super().__init__("coll_version_pin_001", "collections", "medium")

    def generate(self, **params):
        self.params = {"collection": "community.general", "spec": ">=8.0.0"}
        self.description = f"""
In your working directory ({self.workdir}), create
collections/pinned_requirements.yml  that requests the collection

    {self.params['collection']}

pinned to version  {self.params['spec']}  (not just the latest).

Install it into  ./collections  with:
    ansible-galaxy collection install -r collections/pinned_requirements.yml -p collections

Confirm the installed version actually satisfies the constraint.
"""
        self.hints = [
            "requirements.yml entries take name: AND version: (a specifier "
            "like '>=8.0.0', not just a bare number).",
            "Check what actually landed with: ansible-galaxy collection "
            "list -p collections",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_exists(res, "collections/pinned_requirements.yml"):
            return res
        self.check_contains(res, "collections/pinned_requirements.yml",
                            self.params["collection"].replace(".", r"\."),
                            f"requirements lists {self.params['collection']}")
        self.check_contains(res, "collections/pinned_requirements.yml",
                            r"version:\s*[\"']?[><=]",
                            "collection is pinned to a version specifier")
        path = self.workdir / "collections/ansible_collections" / \
            self.params["collection"].replace(".", "/")
        res.add(f"{self.params['collection']} installed under ./collections",
                path.is_dir(), "" if path.is_dir() else
                "ansible-galaxy collection install -r "
                "collections/pinned_requirements.yml -p collections")
        return res
