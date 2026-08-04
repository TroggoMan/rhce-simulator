"""Domain 3: loops and conditionals."""

import random

from core.registry import TaskRegistry
from tasks.base import AnsibleTask


@TaskRegistry.register("flow_control")
class LoopDirectoriesTask(AnsibleTask):
    def __init__(self):
        super().__init__("fc_loop_dirs_001", "flow_control", "easy")

    def generate(self, **params):
        base = params.get("base") or random.choice(["/opt/site", "/srv/project"])
        names = params.get("names") or random.sample(
            ["alpha", "beta", "gamma", "static", "media", "logs"], 3)
        self.params = {"base": base, "names": names}
        listing = "\n".join(f"      {base}/{n}" for n in names)
        self.description = f"""
Create a playbook  loop_dirs.yml  in your working directory ({self.workdir})
that creates these directories on ALL managed nodes using a SINGLE task
with a loop:

{listing}

Each directory must be owned by root with mode 0775. Idempotent.
"""
        self.hints = [
            "file module with loop: and {{ item }} in the path.",
            "Quote '0775' — unquoted YAML octals are a classic exam trap.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "loop_dirs.yml", r"loop:|with_items:",
                            "playbook uses a loop")
        if not self.check_playbook_runs(res, "loop_dirs.yml"):
            return res
        for name in self.params["names"]:
            path = f"{self.params['base']}/{name}"
            self.check_node_state(res, f"{path} exists with mode 0775",
                                  "all", "ansible.builtin.command",
                                  f"stat -c %a {path}", expect=r"\b775\b",
                                  become=True)
        return res


@TaskRegistry.register("flow_control")
class ConditionalInstallTask(AnsibleTask):
    def __init__(self):
        super().__init__("fc_conditional_001", "flow_control", "medium")

    def generate(self, **params):
        threshold = params.get("threshold") or random.choice([512, 768, 1024])
        self.params = {"threshold": threshold, "pkg": "mariadb-server"}
        self.description = f"""
Create a playbook  conditional.yml  in your working directory
({self.workdir}) that runs on ALL managed nodes and:

  * installs  mariadb-server  ONLY on hosts with more than {threshold} MB
    of total memory
  * on hosts with less memory, instead prints the message
    "not enough memory on <short hostname>" using the debug module

The playbook must run without failures on every host either way.
"""
        self.hints = [
            "when: ansible_facts['memtotal_mb'] > " + str(threshold),
            "The debug task needs the opposite condition — mutually exclusive whens.",
            "Facts are integers; don't quote the comparison value.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "conditional.yml", r"when:",
                            "playbook uses conditionals")
        self.check_contains(res, "conditional.yml", r"memtotal",
                            "condition tests total memory fact")
        self.check_playbook_runs(res, "conditional.yml")
        return res


@TaskRegistry.register("flow_control")
class DictLoopPackagesTask(AnsibleTask):
    """Looping over a dict with dict2items — a different loop shape than
    looping over a plain list, and a real exam trap on its own."""

    def __init__(self):
        super().__init__("fc_dict_loop_001", "flow_control", "medium")

    def generate(self, **params):
        present = params.get("present") or random.choice(["tree", "htop"])
        absent = params.get("absent") or random.choice(["telnet", "talk"])
        self.params = {"present": present, "absent": absent}
        self.description = f"""
Create a playbook  dict_loop.yml  in your working directory
({self.workdir}) that, on ALL managed nodes, uses a SINGLE package task
looping over a DICTIONARY variable to reach mixed target states:

    package_state:
      {present}: present
      {absent}: absent

That is: {present} ends up INSTALLED, {absent} ends up REMOVED, both via
one looped task (not two separate package tasks).

Idempotent.
"""
        self.hints = [
            "loop: \"{{ package_state | dict2items }}\" gives you item.key "
            "and item.value in the loop body.",
            "ansible.builtin.dnf: name: \"{{ item.key }}\"  state: \"{{ item.value }}\"",
            "dict2items is the filter that turns a mapping into a list of "
            "{key, value} pairs a loop can consume.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "dict_loop.yml", r"dict2items",
                            "playbook uses dict2items to loop over a dict")
        self.check_contains(res, "dict_loop.yml", r"item\.key",
                            "loop body references item.key")
        if not self.check_playbook_runs(res, "dict_loop.yml"):
            return res
        self.check_node_state(res, f"{self.params['present']} is installed",
                              "all", "ansible.builtin.command",
                              f"rpm -q {self.params['present']}",
                              expect=rf"{self.params['present']}-\d", become=True)
        self.check_node_state(res, f"{self.params['absent']} is NOT installed",
                              "all", "ansible.builtin.shell",
                              f"rpm -q {self.params['absent']} && echo PRESENT || echo GONE",
                              expect=r"GONE", become=True)
        return res


@TaskRegistry.register("flow_control")
class LoopIndexTask(AnsibleTask):
    """loop_control: index_var — numbering loop iterations, a small but
    frequently-tested piece of loop syntax beyond the plain item."""

    def __init__(self):
        super().__init__("fc_loop_index_001", "flow_control", "easy")

    def generate(self, **params):
        base = params.get("base") or random.choice(["/opt/slots", "/srv/queue"])
        names = params.get("names") or random.sample(
            ["north", "south", "east", "west", "central"], 3)
        self.params = {"base": base, "names": names}
        listing = "\n".join(f"      slot{i}_{n} -> {base}/slot{i}_{n}.txt"
                            for i, n in enumerate(names))
        self.description = f"""
Create a playbook  loop_index.yml  in your working directory
({self.workdir}) that, on ALL managed nodes, loops over this list:

    {names}

using a SINGLE task with  loop_control: index_var  to create one file
per item, named using BOTH the index and the item value:

{listing}

Each file's content must be exactly its own item's name. Idempotent.
"""
        self.hints = [
            "loop_control: { index_var: idx } — then use {{ idx }} inside "
            "the loop body alongside {{ item }}.",
            "file/copy dest: \"{{ base }}/slot{{ idx }}_{{ item }}.txt\"",
            "Create the base directory first (a separate task) — the loop "
            "only creates files, not the parent directory.",
        ]
        return self

    def validate(self):
        res = self.result()
        self.check_contains(res, "loop_index.yml", r"index_var",
                            "playbook uses loop_control: index_var")
        if not self.check_playbook_runs(res, "loop_index.yml"):
            return res
        for i, name in enumerate(self.params["names"]):
            path = f"{self.params['base']}/slot{i}_{name}.txt"
            self.check_node_state(res, f"{path} exists with content {name}",
                                  "all", "ansible.builtin.command",
                                  f"cat {path}", expect=rf"^{name}$", become=True)
        return res
