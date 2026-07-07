"""Domain 4: Jinja2 templates."""

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
