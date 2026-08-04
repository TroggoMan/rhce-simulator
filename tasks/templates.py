"""Domain 4: Jinja2 templates."""

import random

from core.registry import TaskRegistry
from tasks.base import AnsibleTask


@TaskRegistry.register("templates")
class MotdTemplateTask(AnsibleTask):
    def __init__(self):
        super().__init__("tpl_motd_001", "templates", "medium")

    def generate(self, **params):
        self.description = f"""
Create a Jinja2 template  motd.j2  and a playbook  motd.yml  in your
working directory ({self.workdir}). The playbook must deploy the template
to  /etc/motd  on ALL managed nodes, producing output of this form
(values from facts, per node):

    System <fqdn> has <memtotal> MB of memory and <processor count> CPUs.

Idempotent — the template only changes the file when its content differs.
"""
        self.hints = [
            "{{ ansible_facts['fqdn'] }}, ['memtotal_mb'], ['processor_count'] (or _vcpus).",
            "template module: src: motd.j2, dest: /etc/motd",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_exists(res, "motd.j2"):
            return res
        self.check_contains(res, "motd.j2", r"\{\{.*(fqdn|hostname).*\}\}",
                            "template uses the fqdn/hostname fact")
        self.check_contains(res, "motd.j2", r"memtotal",
                            "template uses the memory fact")
        self.check_contains(res, "motd.yml", r"template\s*:|ansible\.builtin\.template",
                            "playbook uses the template module")
        if not self.check_playbook_runs(res, "motd.yml"):
            return res
        self.check_node_state(res, "/etc/motd rendered with real values",
                              "all", "ansible.builtin.command", "cat /etc/motd",
                              expect=r"System \S+ has \d+ MB", become=True)
        return res


@TaskRegistry.register("templates")
class HostsFileTemplateTask(AnsibleTask):
    def __init__(self):
        super().__init__("tpl_hosts_001", "templates", "hard")

    def generate(self, **params):
        self.params = {"dest": "/etc/myhosts"}
        self.description = f"""
The classic exam finisher. In your working directory ({self.workdir}):

  1. Create a template  hosts.j2  that generates lines in /etc/hosts
     format — one line per host in the inventory group  all :

        <ip address> <fqdn> <short hostname>

     using each host's facts (hostvars). Fact gathering for every host
     must have happened before rendering.
  2. Create a playbook  hosts.yml  that deploys it to  {self.params['dest']}
     on ALL managed nodes.

Every inventory host must appear in the rendered file on every node.
"""
        self.hints = [
            "{% for host in groups['all'] %} … {% endfor %}",
            "hostvars[host]['ansible_facts']['default_ipv4']['address'] etc.",
            "Facts for OTHER hosts exist only if the play gathered them — run the "
            "play against all hosts (or add a fact-gathering play first).",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_exists(res, "hosts.j2"):
            return res
        self.check_contains(res, "hosts.j2", r"\{%\s*for\s+\w+\s+in\s+groups",
                            "template loops over an inventory group")
        self.check_contains(res, "hosts.j2", r"hostvars",
                            "template reads per-host facts via hostvars")
        if not self.check_playbook_runs(res, "hosts.yml"):
            return res
        for node in self.nodes:
            self.check_node_state(res, f"rendered file mentions {node}",
                                  "all", "ansible.builtin.command",
                                  f"cat {self.params['dest']}", expect=node,
                                  become=True)
        return res


@TaskRegistry.register("templates")
class TemplateGroupConditionalTask(AnsibleTask):
    """{% if %} inside a template, keyed on the RENDERING host's own group
    membership — different content per host from one template file."""

    def __init__(self):
        super().__init__("tpl_conditional_001", "templates", "medium")

    def generate(self, **params):
        self.params = {"dest": "/etc/environment_banner"}
        self.description = f"""
Create a Jinja2 template  banner.j2  and a playbook  banner.yml  in your
working directory ({self.workdir}). Deploy the template to
{self.params['dest']}  on ALL managed nodes, but the RENDERED CONTENT
must differ by group membership — inside the TEMPLATE itself (one file,
not two):

  * hosts in the  dev   inventory group get the line:  ENVIRONMENT=development
  * hosts in the  prod  inventory group get the line:  ENVIRONMENT=production
  * a host in neither group gets:  ENVIRONMENT=unknown

Use  {{% if %}} / {{% elif %}} / {{% else %}}  inside banner.j2 — do not
solve this with two templates or a when: on the deploy task.

Idempotent.
"""
        self.hints = [
            "{% if 'dev' in group_names %}...{% elif 'prod' in group_names %}"
            "...{% else %}...{% endif %} — group_names is available inside "
            "templates exactly like in playbooks.",
            "One template task in the playbook, no when: needed — the "
            "branching lives entirely in the .j2 file.",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_exists(res, "banner.j2"):
            return res
        self.check_contains(res, "banner.j2", r"\{%\s*if\s",
                            "template branches with {% if %}")
        self.check_contains(res, "banner.j2", r"group_names",
                            "template branch tests group_names")
        if not self.check_playbook_runs(res, "banner.yml"):
            return res
        self.check_node_state(res, "dev hosts render ENVIRONMENT=development",
                              "dev", "ansible.builtin.command",
                              f"cat {self.params['dest']}",
                              expect=r"ENVIRONMENT=development", become=True)
        self.check_node_state(res, "prod hosts render ENVIRONMENT=production",
                              "prod", "ansible.builtin.command",
                              f"cat {self.params['dest']}",
                              expect=r"ENVIRONMENT=production", become=True)
        return res


@TaskRegistry.register("templates")
class TemplateFilterListTask(AnsibleTask):
    """Rendering a LIST variable through a Jinja2 filter chain into a
    single config line — join/sort/unique, the filters that turn a list
    variable into text a config file actually wants."""

    def __init__(self):
        super().__init__("tpl_filter_list_001", "templates", "medium")

    def generate(self, **params):
        users = params.get("users") or random.sample(
            ["natasha", "harry", "fred", "sarah", "amr"], 3)
        self.params = {"users": sorted(users), "dest": "/etc/motd.d/allowed_users"}
        self.description = f"""
Create a Jinja2 template  allowed_users.j2  and a playbook
allowed_users.yml  in your working directory ({self.workdir}). Define a
list variable:

    allowed_users:
{chr(10).join(f"      - {u}" for u in users)}

Deploy the rendered template to  {self.params['dest']}  on ALL managed
nodes, producing exactly ONE line:

    ALLOWED_USERS={" ".join(sorted(users))}

The names must appear SORTED ALPHABETICALLY and space-separated — achieve
the sort and joining with Jinja2 FILTERS in the template (  | sort | join
), not by hand-ordering the variable definition.

Idempotent.
"""
        self.hints = [
            "{{ allowed_users | sort | join(' ') }} inside the template.",
            "sort and join are plain Jinja2 filters — no custom code needed.",
            "Define allowed_users in whatever order you like; the template "
            "is what's required to sort it.",
        ]
        return self

    def validate(self):
        res = self.result()
        if not self.check_exists(res, "allowed_users.j2"):
            return res
        self.check_contains(res, "allowed_users.j2", r"\|\s*sort",
                            "template uses the sort filter")
        self.check_contains(res, "allowed_users.j2", r"\|\s*join",
                            "template uses the join filter")
        if not self.check_playbook_runs(res, "allowed_users.yml"):
            return res
        expected = " ".join(self.params["users"])
        self.check_node_state(res, f"{self.params['dest']} has the sorted, joined list",
                              "all", "ansible.builtin.command",
                              f"cat {self.params['dest']}",
                              expect=rf"ALLOWED_USERS={expected}", become=True)
        return res
