"""
Real study content for --learn mode, keyed by task category (see
settings.CATEGORY_TO_DOMAIN / CATEGORY_DISPLAY for how categories map to
exam domains). Unlike config/exam_objectives.py (what Red Hat says the
exam covers), this is teaching material: concept explanations, real module
syntax with working examples, the mistakes that actually cost people
points, and exam-specific tips.

Sourced from Ansible's own current documentation and cross-checked against
a 2026-07-23 research pass on module locations/deprecations — notably:
ansible.posix.firewalld (not ansible.builtin), community.general.lvol/lvg
(not ansible.builtin or ansible.posix), RHEL System Roles' current ~40+
role catalog, vault-ID as the current mainstream Vault pattern, and
RHEL 10 defaulting to dnf5 (ansible.builtin.dnf needs python3-dnf to keep
working against it).

Every category should have an entry here; core/learn.py falls back to
just the raw objective bullets for anything missing rather than crashing.
"""

CONTENT = {
    "ansible_config": {
        "explanation": (
            "ansible.cfg controls Ansible's own behavior (inventory path, "
            "remote user, privilege escalation, host key checking); "
            "ansible-navigator.yml controls the navigator wrapper "
            "specifically (execution mode, execution environments). "
            "Ansible reads config in this precedence order: the "
            "ANSIBLE_CONFIG env var, then ./ansible.cfg in your CURRENT "
            "directory, then ~/.ansible.cfg, then /etc/ansible/ansible.cfg "
            "— only the first one found is used, they don't merge."
        ),
        "commands": [
            {
                "name": "Generate a fully-commented reference file",
                "syntax": "ansible-config init --disabled > ansible.cfg",
                "example": "ansible-config init --disabled > ansible.cfg",
                "notes": "--disabled comments out every setting so you can "
                         "uncomment just what you need instead of writing "
                         "the file from memory.",
            },
            {
                "name": "Prove your config actually took effect",
                "syntax": "ansible-config dump --only-changed",
                "example": "ansible-config dump --only-changed",
                "notes": "Shows only settings that differ from Ansible's "
                         "built-in defaults — the fastest way to catch a "
                         "typo'd key name, which Ansible otherwise ignores "
                         "silently instead of erroring.",
            },
            {
                "name": "[defaults] essentials",
                "syntax": "[defaults]\ninventory = ./inventory\n"
                          "remote_user = devops\nhost_key_checking = False",
                "example": "[defaults]\ninventory = ./inventory\n"
                          "remote_user = devops\nhost_key_checking = False",
                "notes": "host_key_checking = False matters most the FIRST "
                         "time you touch fresh managed nodes — without it "
                         "the first connection hangs on an interactive "
                         "yes/no prompt with no TTY to answer it.",
            },
            {
                "name": "[privilege_escalation]",
                "syntax": "[privilege_escalation]\nbecome = True\n"
                          "become_method = sudo\nbecome_ask_pass = False",
                "example": "[privilege_escalation]\nbecome = True\n"
                          "become_method = sudo\nbecome_ask_pass = False",
                "notes": "become = True here makes every task escalate by "
                         "default — you don't have to set become: true "
                         "per-task.",
            },
            {
                "name": "ansible-navigator.yml skeleton",
                "syntax": "ansible-navigator:\n  mode: stdout\n"
                          "  playbook-artifacts:\n    enable: false\n"
                          "  execution-environment:\n    pull:\n      "
                          "policy: missing",
                "example": "ansible-navigator:\n  mode: stdout\n"
                          "  playbook-artifacts:\n    enable: false\n"
                          "  execution-environment:\n    pull:\n      "
                          "policy: missing",
                "notes": "policy: missing stops navigator trying to pull a "
                         "fresh execution-environment image on every single "
                         "run — it only pulls if the image isn't already "
                         "present locally.",
            },
        ],
        "common_mistakes": [
            "Assuming ansible.cfg is read from the playbook's directory — "
            "it's read from your CURRENT working directory, full stop.",
            "become = true with no matching passwordless sudo actually "
            "configured on the managed node — the config being 'correct' "
            "doesn't mean escalation will succeed.",
        ],
        "exam_tips": [
            "Do this first, always — every task after it depends on the "
            "inventory path and remote_user being right.",
            "Before ansible.cfg exists (or while you're still writing it), "
            "every command needs its defaults spelled out by hand: "
            "-i inventory (which inventory), -u <user> (which remote "
            "user), -b (become/sudo), --ssh-common-args="
            "'-o StrictHostKeyChecking=no' (skip the first-connection host "
            "key prompt). Nothing is 'broken' without ansible.cfg — you're "
            "just typing what it would otherwise default to.",
        ],
    },
    "inventory": {
        "explanation": (
            "A static inventory defines hosts and groups. INI-style groups "
            "are [groupname] headers followed by hostnames; [group:vars] "
            "attaches variables to every host in a group; [group:children] "
            "builds a group out of OTHER groups instead of listing hosts "
            "directly."
        ),
        "commands": [
            {
                "name": "Basic groups",
                "syntax": "[web]\nhost1\nhost2\n\n[db]\nhost3",
                "example": "[dev]\n192.168.1.10\n\n[prod]\n192.168.1.20",
                "notes": "A trailing blank line between groups is just "
                         "convention, not required — but stray whitespace "
                         "INSIDE a [group] header line breaks parsing.",
            },
            {
                "name": "Group of groups (children)",
                "syntax": "[webservers:children]\ndev\nprod",
                "example": "[webservers:children]\ndev\nprod",
                "notes": "Don't repeat hostnames across groups — nest the "
                         "existing groups instead. Every child group named "
                         "here must be defined somewhere in the file, even "
                         "if it ends up empty.",
            },
            {
                "name": "Local connection for the control node itself",
                "syntax": "localhost ansible_connection=local",
                "example": "[control]\nlocalhost ansible_connection=local",
                "notes": "Without this, Ansible tries to SSH to localhost, "
                         "which usually fails or is needlessly slow.",
            },
            {
                "name": "Verify the structure parsed correctly",
                "syntax": "ansible-inventory --graph",
                "example": "ansible-inventory --graph",
                "notes": "Shows the resolved group tree — the fastest way "
                         "to catch a children-group typo before it costs "
                         "you a whole task's validation.",
            },
        ],
        "common_mistakes": [
            "A [group:children] section listing a group name that's never "
            "actually defined as its own [group] header anywhere.",
            "Assuming group vars set in [group:vars] override host-specific "
            "vars — precedence actually runs the other way.",
            "Building only the groups the ONE task in front of you asks "
            "for. Several tasks elsewhere in this catalog (file content, "
            "playbooks, templates, error handling) assume dev and prod "
            "groups already exist, each with at least one host — which "
            "specific node goes in which doesn't matter for grading, only "
            "that both resolve to something. Add them up front, not "
            "task-by-task, or a later task fails on a missing group, not a "
            "wrong playbook.",
        ],
        "exam_tips": [
            "ansible <group> -m ping is the single fastest sanity check "
            "before writing a single line of playbook against that group.",
        ],
    },
    "managed_nodes": {
        "explanation": (
            "Before anything else can run unattended, managed nodes need "
            "key-based SSH access and passwordless privilege escalation "
            "configured for whatever user Ansible will connect as. The "
            "authorized_key module (ansible.posix) is how you do that "
            "WITH Ansible instead of manually running ssh-copy-id on every "
            "host by hand.\n\n"
            "This simulator's own lab scripts (lab-setup.sh, vm-lab-setup.sh) "
            "deliberately hand you nothing but root + a password on each "
            "node — the same bootstrap state the real exam gives you. There "
            "is no baseline inventory, no automation user, no key. Getting "
            "from 'root, reachable by password' to 'a working, key-based "
            "Ansible setup' is a two-phase move: connect ONCE using "
            "password auth to bootstrap your own user/key/sudoers, then "
            "switch your inventory over to that and never touch a password "
            "again."
        ),
        "commands": [
            {
                "name": "Phase 1 — bootstrap over password auth (one-time)",
                "syntax": "ansible all -m ping -u root -k \\\n"
                          "  -e ansible_python_interpreter=/usr/bin/python3 \\\n"
                          "  --ssh-common-args='-o StrictHostKeyChecking=no'",
                "example": "ansible all -m ping -u root -k \\\n"
                          "  -e ansible_python_interpreter=/usr/bin/python3 \\\n"
                          "  --ssh-common-args='-o StrictHostKeyChecking=no'",
                "notes": "-k prompts for the SSH password interactively — "
                         "this is the ONLY time a password is typed anywhere "
                         "near Ansible. It needs an inventory that already "
                         "lists the nodes (host/port/root), even though "
                         "nothing else about access works yet.",
            },
            {
                "name": "Phase 1 — push a key + create the automation user, "
                        "still over password auth",
                "syntax": "ansible-playbook bootstrap.yml -u root -k",
                "example": "ansible-playbook bootstrap.yml -u root -k",
                "notes": "bootstrap.yml is a playbook YOU write: "
                         "ansible.builtin.user to create the automation "
                         "user, ansible.posix.authorized_key to install "
                         "YOUR pubkey, a sudoers.d drop-in for passwordless "
                         "sudo. It connects as root (still password-based) "
                         "specifically so it can set up everything after it "
                         "won't need to.",
            },
            {
                "name": "Phase 2 — switch over, never use a password again",
                "syntax": "# inventory: ansible_user=<your user> "
                          "ansible_ssh_private_key_file=<your key>\n"
                          "ansible all -m ping",
                "example": "# inventory: ansible_user=devops "
                          "ansible_ssh_private_key_file=~/.ssh/id_ed25519\n"
                          "ansible all -m ping",
                "notes": "Once this pings clean with NO -k, NO -u root, and "
                         "NO password anywhere, bootstrap is done — every "
                         "other task in this catalog grades against "
                         "whatever inventory/ansible.cfg you just built.",
            },
            {
                "name": "Distribute a public key",
                "syntax": "ansible.posix.authorized_key:\n  user: devops\n"
                          "  state: present\n"
                          "  key: \"{{ lookup('file', 'id_ed25519.pub') }}\"",
                "example": "ansible.posix.authorized_key:\n  user: devops\n"
                          "  state: present\n"
                          "  key: \"{{ lookup('file', "
                          "'keys/id_practice.pub') }}\"",
                "notes": "lookup('file', ...) reads a file on the CONTROL "
                         "node at run time — you never paste key text "
                         "directly into the playbook.",
            },
            {
                "name": "Safe sudoers drop-in",
                "syntax": "ansible.builtin.copy:\n"
                          "  content: '%wheel ALL=(ALL) NOPASSWD: ALL'\n"
                          "  dest: /etc/sudoers.d/wheel\n"
                          "  mode: '0440'\n  validate: 'visudo -cf %s'",
                "example": "ansible.builtin.copy:\n"
                          "  content: '%opsadmin ALL=(ALL) NOPASSWD: ALL'\n"
                          "  dest: /etc/sudoers.d/opsadmin\n"
                          "  mode: '0440'\n  validate: 'visudo -cf %s'",
                "notes": "validate: runs against a TEMP file before it's "
                         "allowed to overwrite the real one — a broken "
                         "sudoers file never actually gets installed.",
            },
        ],
        "common_mistakes": [
            "Manually ssh-ing in or installing sshpass to handle the "
            "password-auth step yourselves — Ansible does this FOR you: "
            "-k prompts for it, -e ansible_password=<pw> supplies it "
            "non-interactively. Either way it's Ansible making the "
            "connection, exactly like every other task. You never need a "
            "raw ssh/sshpass command anywhere in this workflow.",
            "0440 is not optional for sudoers.d files — sudo refuses to "
            "even read a group- or world-writable sudoers file.",
            "Skipping validate: — one bad line here can lock out sudo on "
            "every managed node at once.",
            "Writing ansible_user/ansible_ssh_private_key_file into the "
            "inventory BEFORE that user or key actually exists on the "
            "nodes — the bootstrap playbook itself has to run with -u root "
            "-k, not through the inventory entry it's busy creating.",
            "Forgetting --ssh-common-args='-o StrictHostKeyChecking=no' "
            "(or host_key_checking = False in ansible.cfg) on a lab you've "
            "just rebuilt — SSH remembers the OLD host key from last time "
            "and refuses to connect to the new one with no TTY to confirm.",
        ],
        "exam_tips": [
            "This is almost always literally task 1 on the real exam — "
            "you're handed root/password access and expected to bootstrap "
            "proper key-based access and passwordless sudo yourself before "
            "anything else will run unattended. Build your dev/prod "
            "inventory groups in this same pass too — see --learn "
            "inventory for why.",
            "-k asks for the SSH password; -K (capital) separately asks "
            "for the BECOME password if the account you're connecting as "
            "needs one for sudo — root doesn't, but a non-root bootstrap "
            "account might. Confusing the two is a common early mistake.",
            "Once your own key-based inventory works, keep it — don't "
            "leave root/password reachable in ansible.cfg 'just in case'. "
            "Password auth is the bootstrap ladder, not the house.",
        ],
    },
    "adhoc": {
        "explanation": (
            "Ad-hoc commands (ansible <pattern> -m <module> -a '<args>') "
            "are for one-off actions; playbooks are for anything "
            "repeatable/idempotent. The exam explicitly tests writing a "
            "SHELL SCRIPT that wraps an ad-hoc command — not a playbook — "
            "so read task wording carefully."
        ),
        "commands": [
            {
                "name": "Basic ad-hoc call",
                "syntax": "ansible <pattern> -m <module> -a '<args>'",
                "example": "ansible all -m ansible.builtin.ping",
                "notes": "",
            },
            {
                "name": "With arguments and privilege escalation",
                "syntax": "ansible web -b -m ansible.builtin.copy "
                          "-a \"dest=/etc/motd content='hi'\"",
                "example": "ansible web -b -m ansible.builtin.copy "
                          "-a \"dest=/etc/motd content='hi'\"",
                "notes": "-b is shorthand for --become.",
            },
            {
                "name": "Pattern tricks",
                "syntax": "ansible 'web:!staging' -m ping",
                "example": "ansible 'web:&prod' -m ping",
                "notes": ": is union, :! is exclusion, :& is intersection "
                         "of inventory groups.",
            },
        ],
        "common_mistakes": [
            "content= adds no trailing newline unless you put one in — a "
            "frequent 'why does this file show changed every run' trap.",
            "-a argument strings with nested quotes are a classic shell "
            "escaping trap — get the quoting wrong and the module never "
            "sees the argument you intended.",
        ],
        "exam_tips": [
            "\"Write a script that uses an ad-hoc command\" means an actual "
            "shell script invoking `ansible ...` — not ansible-playbook.",
        ],
    },
    "navigator": {
        "explanation": (
            "ansible-navigator runs ansible-playbook/ansible-inventory/"
            "ansible-doc through an execution environment (a container "
            "bundling ansible-core + collections), and is the exam's "
            "primary interface, not a bonus tool. It now ships as part of "
            "the ansible-dev-tools bundle rather than standalone, but "
            "nothing about how you use it has changed."
        ),
        "commands": [
            {
                "name": "Run a playbook",
                "syntax": "ansible-navigator run <playbook> --mode stdout",
                "example": "ansible-navigator run site.yml --mode stdout",
                "notes": "Without --mode stdout you land in the "
                         "interactive TUI, which looks 'stuck' if you're "
                         "not expecting it (press q to quit).",
            },
            {
                "name": "Look up a module (finding new modules in "
                        "collections)",
                "syntax": "ansible-navigator doc <fqcn> --mode stdout",
                "example": "ansible-navigator doc ansible.posix.firewalld "
                          "--mode stdout",
                "notes": "",
            },
            {
                "name": "Browse a resolved inventory",
                "syntax": "ansible-navigator inventory -i inventory "
                          "--mode stdout",
                "example": "ansible-navigator inventory -i inventory "
                          "--mode stdout",
                "notes": "",
            },
            {
                "name": "Run without an execution environment",
                "syntax": "ansible-navigator run <playbook> --ee false "
                          "--mode stdout",
                "example": "ansible-navigator run site.yml --ee false "
                          "--mode stdout",
                "notes": "Useful when podman/the EE image aren't "
                         "available, but note this diverges from the "
                         "exam's normal (EE-based) workflow.",
            },
        ],
        "common_mistakes": [
            "Not realizing navigator defaults to pulling/using an "
            "execution environment — if that image can't be reached, runs "
            "fail with an error that doesn't obviously say 'network/EE "
            "problem' unless you know to look.",
        ],
        "exam_tips": [
            "Bake mode: stdout and pull policy: missing into "
            "ansible-navigator.yml once instead of retyping flags on "
            "every command.",
        ],
    },
    "source_control": {
        "explanation": (
            "Basic Git operations (clone, add, commit, push) are now an "
            "explicit part of the objectives, alongside being able to do "
            "the same from inside VS Code specifically. The underlying "
            "commands are identical no matter which editor drives them, "
            "which is what actually gets graded."
        ),
        "commands": [
            {
                "name": "Clone",
                "syntax": "git clone <url-or-path> <dir>",
                "example": "git clone /srv/git/ansible-content.git lab_repo",
                "notes": "",
            },
            {
                "name": "Stage and commit",
                "syntax": "git add <file> && git commit -m '<message>'",
                "example": "git add site.yml && git commit -m "
                          "'add web playbook'",
                "notes": "commit only includes what was staged with add — "
                         "a forgotten add means nothing new gets committed, "
                         "silently.",
            },
            {
                "name": "Push",
                "syntax": "git push origin <branch>",
                "example": "git push origin main",
                "notes": "",
            },
            {
                "name": "Sanity-check before you trust it",
                "syntax": "git status && git log --oneline",
                "example": "git status && git log --oneline",
                "notes": "",
            },
        ],
        "common_mistakes": [
            "Running git commands from the wrong directory — git always "
            "operates on whichever repo contains your CURRENT directory, "
            "not your Ansible working directory.",
            "Forgetting git add before commit — the commit succeeds but "
            "contains nothing new.",
        ],
        "exam_tips": [
            "The exam's Git ask is intentionally basic — clone, add, "
            "commit, push. Don't over-invest in branching/rebasing; prove "
            "you can get a playbook into version control, that's the "
            "whole objective.",
        ],
    },
    "playbook_basics": {
        "explanation": (
            "A playbook is a list of plays; a play is hosts: + tasks:. "
            "Module choice matters: state: present is idempotent, "
            "state: latest usually isn't. On RHEL 10 / Rocky 10, dnf5 is "
            "the default backend — ansible.builtin.dnf still works but "
            "needs the python3-dnf compat package installed on the "
            "managed node, or use ansible.builtin.package for a module "
            "that's portable across dnf/yum/apt without caring which."
        ),
        "commands": [
            {
                "name": "Install a package",
                "syntax": "ansible.builtin.dnf:\n  name: httpd\n"
                          "  state: present",
                "example": "ansible.builtin.dnf:\n  name: httpd\n"
                          "  state: present",
                "notes": "state: present is idempotent; state: latest can "
                         "report changed on every run once a newer build "
                         "exists upstream, which breaks idempotence checks.",
            },
            {
                "name": "Portable package install",
                "syntax": "ansible.builtin.package:\n  name: httpd\n"
                          "  state: present",
                "example": "ansible.builtin.package:\n  name: httpd\n"
                          "  state: present",
                "notes": "Works unmodified across dnf/dnf5/yum/apt hosts — "
                         "the safer default whenever you don't need a "
                         "dnf-specific option.",
            },
            {
                "name": "Service, enabled AND started",
                "syntax": "ansible.builtin.service:\n  name: httpd\n"
                          "  state: started\n  enabled: true",
                "example": "ansible.builtin.service:\n  name: httpd\n"
                          "  state: started\n  enabled: true",
                "notes": "enabled: true is what survives a reboot — "
                         "state: started alone does not, and Red Hat's "
                         "performance exams explicitly grade post-reboot "
                         "state.",
            },
            {
                "name": "Firewall rule",
                "syntax": "ansible.posix.firewalld:\n  service: http\n"
                          "  permanent: true\n  immediate: true\n"
                          "  state: enabled",
                "example": "ansible.posix.firewalld:\n  service: http\n"
                          "  permanent: true\n  immediate: true\n"
                          "  state: enabled",
                "notes": "Lives in the ansible.posix collection, NOT "
                         "ansible.builtin — a common wrong guess. "
                         "permanent + immediate together mirror "
                         "firewall-cmd's --permanent plus a live reload.",
            },
        ],
        "common_mistakes": [
            "shell/command tasks standing in for a real module — they're "
            "rarely idempotent, and a re-run of the grading playbook will "
            "show changed every single time.",
            "state: latest where state: present was actually wanted.",
        ],
        "exam_tips": [
            "\"Convert this shell script to a playbook\" tasks are graded "
            "on using PROPER modules, not shell/command tasks wrapping the "
            "same commands — that defeats the point of the exercise.",
        ],
    },
    "variables_facts": {
        "explanation": (
            "Facts are gathered automatically per host (the setup module) "
            "and exposed under ansible_facts[...]; register captures ANY "
            "task's result into a variable for later use in the same play."
        ),
        "commands": [
            {
                "name": "See what facts a host actually has",
                "syntax": "ansible <host> -m ansible.builtin.setup",
                "example": "ansible node1 -m ansible.builtin.setup "
                          "| less",
                "notes": "Fastest way to find an exact fact key name "
                         "instead of guessing.",
            },
            {
                "name": "Use a fact",
                "syntax": "\"{{ ansible_facts['memtotal_mb'] }}\"",
                "example": "\"{{ ansible_facts['memtotal_mb'] }}\"",
                "notes": "",
            },
            {
                "name": "Register a command's output",
                "syntax": "- ansible.builtin.command: df -h /\n"
                          "  register: disk_out\n  changed_when: false",
                "example": "- ansible.builtin.command: df -h /\n"
                          "  register: disk_out\n  changed_when: false",
                "notes": "changed_when: false on a read-only command stops "
                         "it always reporting changed and breaking "
                         "idempotence checks on a task that genuinely "
                         "changed nothing.",
            },
            {
                "name": "Fallback for a missing value",
                "syntax": "\"{{ ansible_facts['bios_version'] | "
                          "default('NONE') }}\"",
                "example": "\"{{ ansible_facts['bios_version'] | "
                          "default('NONE') }}\"",
                "notes": "",
            },
        ],
        "common_mistakes": [
            "Forgetting changed_when: false on read-only command/shell "
            "tasks.",
            "Reading hostvars for a host that was never part of the "
            "current (or an earlier) play — its facts were simply never "
            "gathered, so the lookup comes back empty, not an error.",
        ],
        "exam_tips": [
            "`ansible <host> -m setup | less` beats guessing a fact name "
            "every time.",
        ],
    },
    "flow_control": {
        "explanation": (
            "loop: iterates a task over a list (the modern replacement for "
            "with_items); when: gates whether a task or whole play runs at "
            "all, evaluated per host."
        ),
        "commands": [
            {
                "name": "Loop over a list",
                "syntax": "ansible.builtin.file:\n"
                          "  path: \"/opt/{{ item }}\"\n"
                          "  state: directory\n  mode: '0775'\n"
                          "loop:\n  - alpha\n  - beta",
                "example": "ansible.builtin.file:\n"
                          "  path: \"/opt/{{ item }}\"\n"
                          "  state: directory\n  mode: '0775'\n"
                          "loop:\n  - alpha\n  - beta",
                "notes": "",
            },
            {
                "name": "Conditional task",
                "syntax": "ansible.builtin.dnf:\n  name: mariadb-server\n"
                          "when: ansible_facts['memtotal_mb'] > 1024",
                "example": "ansible.builtin.dnf:\n  name: mariadb-server\n"
                          "when: ansible_facts['memtotal_mb'] > 1024",
                "notes": "Facts like memtotal_mb are numeric — don't "
                         "quote the comparison value.",
            },
            {
                "name": "Loop + when together",
                "syntax": "loop: \"{{ users }}\"\n"
                          "when: item.job == 'developer'",
                "example": "loop: \"{{ users }}\"\n"
                          "when: item.job == 'developer'",
                "notes": "when: is evaluated separately for EACH item in "
                         "the loop, not once for the whole loop.",
            },
        ],
        "common_mistakes": [
            "Unquoted octal file modes — write '0775', not 0775; a "
            "leading-zero unquoted number can parse unexpectedly in YAML.",
            "Two when: branches that were meant to be mutually exclusive "
            "but actually leave a gap (or overlap) for some hosts.",
        ],
        "exam_tips": [
            "When a task wants two branches covering every host (over a "
            "threshold / at-or-under it), write out both when: conditions "
            "explicitly rather than relying on an implicit else.",
        ],
    },
    "error_handling": {
        "explanation": (
            "Handlers run once, at the END of the play, and only if "
            "notified by a task that reported changed. block/rescue/"
            "always give try/except/finally-style control within a play — "
            "a rescued failure does NOT fail the play.\n\n"
            "The other half of error handling is telling Ansible what "
            "success and change actually MEAN for a given task. Real "
            "modules work that out themselves; command and shell cannot. "
            "They call a task failed purely because the exit code was "
            "non-zero, and they report 'changed' every single time they "
            "run, because they have no idea whether they changed "
            "anything. failed_when and changed_when are how you correct "
            "both — and without changed_when, a single command task makes "
            "an otherwise perfect playbook fail an idempotence check."
        ),
        "commands": [
            {
                "name": "Handler",
                "syntax": "tasks:\n  - ansible.builtin.template:\n"
                          "      src: httpd.conf.j2\n"
                          "      dest: /etc/httpd/conf/httpd.conf\n"
                          "    notify: restart httpd\n"
                          "handlers:\n  - name: restart httpd\n"
                          "    ansible.builtin.service:\n"
                          "      name: httpd\n      state: restarted",
                "example": "tasks:\n  - ansible.builtin.template:\n"
                          "      src: httpd.conf.j2\n"
                          "      dest: /etc/httpd/conf/httpd.conf\n"
                          "    notify: restart httpd\n"
                          "handlers:\n  - name: restart httpd\n"
                          "    ansible.builtin.service:\n"
                          "      name: httpd\n      state: restarted",
                "notes": "The handlers: name must match notify: exactly.",
            },
            {
                "name": "block / rescue / always",
                "syntax": "- block:\n    - ansible.builtin.command: "
                          "/bin/false\n  rescue:\n    - "
                          "ansible.builtin.file:\n        path: "
                          "/var/tmp/rescue_ran\n        state: touch\n"
                          "  always:\n    - ansible.builtin.file:\n"
                          "        path: /var/tmp/always_ran\n"
                          "        state: touch",
                "example": "- block:\n    - ansible.builtin.command: "
                          "/bin/false\n  rescue:\n    - "
                          "ansible.builtin.file:\n        path: "
                          "/var/tmp/rescue_ran\n        state: touch\n"
                          "  always:\n    - ansible.builtin.file:\n"
                          "        path: /var/tmp/always_ran\n"
                          "        state: touch",
                "notes": "",
            },
            {
                "name": "changed_when — stop lying about changes",
                "syntax": "- ansible.builtin.command: grep -q OK /etc/app.conf\n"
                          "  register: audit\n"
                          "  changed_when: false",
                "example": "- ansible.builtin.command: grep -q OK /etc/app.conf\n"
                          "  register: audit\n"
                          "  changed_when: false",
                "notes": "A command that only READS never changes anything, "
                         "but Ansible reports it changed on every run. "
                         "changed_when: false is what makes a playbook "
                         "containing command/shell tasks idempotent — it is "
                         "the most commonly forgotten line on the exam.",
            },
            {
                "name": "failed_when — define what failure means",
                "syntax": "- ansible.builtin.command: grep OK /etc/app.conf\n"
                          "  register: audit\n"
                          "  failed_when: audit.rc not in [0, 1]\n"
                          "  changed_when: false",
                "example": "- ansible.builtin.command: grep OK /etc/app.conf\n"
                          "  register: audit\n"
                          "  failed_when: audit.rc not in [0, 1]\n"
                          "  changed_when: false",
                "notes": "grep exits 1 for 'no match' and 2 for a real "
                         "error. Only 2 is a failure. failed_when lets you "
                         "say so precisely, instead of suppressing "
                         "everything with ignore_errors.",
            },
            {
                "name": "ignore_errors — the blunt instrument",
                "syntax": "- ansible.builtin.command: /might/not/exist\n"
                          "  ignore_errors: true",
                "example": "- ansible.builtin.command: /might/not/exist\n"
                          "  ignore_errors: true",
                "notes": "Suppresses EVERY failure, including the ones you "
                         "wanted to hear about. Prefer failed_when whenever "
                         "you can express the real condition — graders "
                         "notice the difference.",
            },
            {
                "name": "assert — state the invariant",
                "syntax": "- ansible.builtin.assert:\n    that:\n"
                          "      - result.rc == 0\n"
                          "    fail_msg: \"deploy failed even with --force\"\n"
                          "    success_msg: \"deploy recovered on retry\"",
                "example": "- ansible.builtin.assert:\n    that:\n"
                          "      - result.rc == 0\n"
                          "    fail_msg: \"deploy failed even with --force\"\n"
                          "    success_msg: \"deploy recovered on retry\"",
                "notes": "that: takes a LIST of conditions, all of which "
                         "must hold. Used inside rescue, it turns 'we tried "
                         "something else' into 'and we proved it worked'.",
            },
        ],
        "common_mistakes": [
            "Expecting a handler to fire mid-play — it always runs at the "
            "END (unless you explicitly flush it with "
            "meta: flush_handlers).",
            "Assuming a rescued failure still fails the play overall — it "
            "doesn't, that's the entire point of rescue.",
            "Leaving changed_when off a read-only command/shell task, then "
            "wondering why the playbook can never report changed=0.",
            "Reaching for ignore_errors: true when failed_when would have "
            "expressed the actual condition — it hides real errors too.",
            "Using a variable registered inside a block that failed, "
            "without | default() — in the always section it may not hold "
            "what you expect, and an undefined reference crashes the play.",
        ],
        "exam_tips": [
            "A playbook can legitimately finish rc=0 on every host even "
            "though a block inside it intentionally failed, as long as "
            "rescue handled it — that's often exactly what's being graded.",
            "Any task you write with command or shell should make you ask "
            "two questions immediately: does it need changed_when, and does "
            "it need failed_when? Usually the answer to at least one is yes.",
        ],
    },
    "selinux": {
        "explanation": (
            "SELinux is a mandatory access control layer: even when normal "
            "file permissions allow something, SELinux can still deny it. "
            "That is why 'the config is right but the service won't work' "
            "is so often an SELinux problem — and why the exam likes it.\n\n"
            "Four things get automated, and they are NOT interchangeable:\n"
            "  * MODE — enforcing / permissive / disabled, system-wide\n"
            "  * BOOLEANS — named on/off switches in the shipped policy\n"
            "  * PORT LABELS — which TCP/UDP ports a service may bind\n"
            "  * FILE CONTEXTS — the label carried by files on disk\n\n"
            "The single most important thing to internalise: adding a file "
            "context RULE does not relabel anything that already exists. "
            "The rule describes what files SHOULD be labelled; restorecon "
            "is what actually applies it. A playbook with only the rule "
            "passes a syntax check and still leaves the service broken.\n\n"
            "Collection trap: these modules are split across two "
            "collections. seboolean and selinux live in ansible.posix; "
            "seport and sefcontext live in community.general. Getting this "
            "backwards is a very common way to waste exam minutes."
        ),
        "commands": [
            {
                "name": "SELinux mode (persistent)",
                "syntax": "- ansible.posix.selinux:\n    policy: targeted\n"
                          "    state: enforcing",
                "example": "- ansible.posix.selinux:\n    policy: targeted\n"
                           "    state: enforcing",
                "notes": "Sets the persistent config in /etc/selinux/config, "
                         "not just the running mode. Moving from DISABLED to "
                         "enforcing requires a reboot and a full relabel; "
                         "permissive <-> enforcing does not. The module "
                         "returning 'reboot required' is a normal result, "
                         "not an error.",
            },
            {
                "name": "Boolean (must be persistent)",
                "syntax": "- ansible.posix.seboolean:\n"
                          "    name: httpd_can_network_connect\n"
                          "    state: true\n    persistent: true",
                "example": "- ansible.posix.seboolean:\n"
                           "    name: httpd_can_network_connect\n"
                           "    state: true\n    persistent: true",
                "notes": "Without persistent: true the setting reverts on "
                         "reboot — and every Red Hat exam requires config to "
                         "survive a reboot. Browse booleans on a node with "
                         "getsebool -a, or semanage boolean -l for "
                         "descriptions.",
            },
            {
                "name": "Port label (custom service ports)",
                "syntax": "- ansible.builtin.dnf:\n"
                          "    name: policycoreutils-python-utils\n"
                          "    state: present\n\n"
                          "- community.general.seport:\n    ports: 8080\n"
                          "    proto: tcp\n    setype: http_port_t\n"
                          "    state: present",
                "example": "- ansible.builtin.dnf:\n"
                           "    name: policycoreutils-python-utils\n"
                           "    state: present\n\n"
                           "- community.general.seport:\n    ports: 8080\n"
                           "    proto: tcp\n    setype: http_port_t\n"
                           "    state: present",
                "notes": "The module shells out to semanage, which comes "
                         "from policycoreutils-python-utils — install it "
                         "first or the task fails on a minimal host. Verify "
                         "with: semanage port -l | grep http_port_t",
            },
            {
                "name": "File context rule + APPLYING it",
                "syntax": "- community.general.sefcontext:\n"
                          "    target: '/srv/www(/.*)?'\n"
                          "    setype: httpd_sys_content_t\n"
                          "    state: present\n\n"
                          "- ansible.builtin.command: restorecon -Rv /srv/www",
                "example": "- community.general.sefcontext:\n"
                           "    target: '/srv/www(/.*)?'\n"
                           "    setype: httpd_sys_content_t\n"
                           "    state: present\n\n"
                           "- ansible.builtin.command: restorecon -Rv /srv/www",
                "notes": "TWO steps, always. (/.*)? is a regex meaning 'this "
                         "directory and everything under it' — omit it and "
                         "you label only the directory itself. sefcontext "
                         "writes the rule; restorecon applies it to files "
                         "already on disk.",
            },
            {
                "name": "Inspecting labels on a node",
                "syntax": "ls -Zd /srv/www          # file/dir context\n"
                          "getenforce               # current mode\n"
                          "getsebool -a | grep httpd\n"
                          "semanage port -l | grep http_port_t",
                "example": "ls -Zd /srv/www          # file/dir context\n"
                           "getenforce               # current mode\n"
                           "getsebool -a | grep httpd\n"
                           "semanage port -l | grep http_port_t",
                "notes": "-Z is the flag that shows SELinux context on ls, "
                         "ps and id. If a service mysteriously won't start, "
                         "check the label before rewriting the config.",
            },
        ],
        "common_mistakes": [
            "Adding a sefcontext rule and never running restorecon — the "
            "policy knows what the label SHOULD be, but the files on disk "
            "still carry the old one, so nothing actually changes.",
            "Omitting persistent: true on a boolean, so it silently reverts "
            "at the next reboot.",
            "Writing the target regex as '/srv/www' instead of "
            "'/srv/www(/.*)?', which labels the directory but none of the "
            "content inside it.",
            "Reaching for community.general.seboolean or "
            "ansible.posix.seport — the two collections are the other way "
            "round for those modules.",
            "Forgetting that seport needs semanage on the managed node "
            "(policycoreutils-python-utils), which minimal images lack.",
        ],
        "exam_tips": [
            "Running a service on a NON-DEFAULT port needs three separate "
            "things and gets no partial credit: the service's own config "
            "(Listen), the firewalld rule, and the SELinux port label. "
            "Miss any one and it doesn't serve.",
            "'Permission denied' where the file permissions are obviously "
            "fine is SELinux until proven otherwise. Confirm quickly by "
            "checking the label with ls -Z rather than guessing.",
            "Never 'fix' an exam task by disabling SELinux. The objectives "
            "assume enforcing, and a task that only works with SELinux off "
            "is a task you failed.",
        ],
    },
    "templates": {
        "explanation": (
            "Jinja2 templates (.j2) render via the template module; loops, "
            "conditionals and facts all work inside {{ }} / {% %}; "
            "hostvars[host] reaches another host's gathered facts, but "
            "only if that host was actually part of a play that gathered "
            "them."
        ),
        "commands": [
            {
                "name": "Deploy a template",
                "syntax": "ansible.builtin.template:\n  src: motd.j2\n"
                          "  dest: /etc/motd",
                "example": "ansible.builtin.template:\n  src: motd.j2\n"
                          "  dest: /etc/motd",
                "notes": "Only writes when rendered content actually "
                         "differs — naturally idempotent.",
            },
            {
                "name": "Loop over inventory in a template",
                "syntax": "{% for host in groups['all'] %}\n"
                          "{{ hostvars[host]['ansible_facts']"
                          "['default_ipv4']['address'] }} {{ host }}\n"
                          "{% endfor %}",
                "example": "{% for host in groups['all'] %}\n"
                          "{{ hostvars[host]['ansible_facts']"
                          "['default_ipv4']['address'] }} {{ host }}\n"
                          "{% endfor %}",
                "notes": "",
            },
            {
                "name": "Interpolate facts",
                "syntax": "System {{ ansible_facts['fqdn'] }} has "
                          "{{ ansible_facts['memtotal_mb'] }} MB",
                "example": "System {{ ansible_facts['fqdn'] }} has "
                          "{{ ansible_facts['memtotal_mb'] }} MB",
                "notes": "",
            },
        ],
        "common_mistakes": [
            "Referencing hostvars for a host that was never targeted/"
            "gathered by the current (or an earlier) play — the lookup "
            "just comes back empty.",
            "Hand-editing the RENDERED destination file to 'fix' bad "
            "output — the next playbook run overwrites it again; fix the "
            ".j2 source instead.",
        ],
        "exam_tips": [
            "The classic 'generate /etc/hosts from the whole inventory' "
            "task is a facts + templates + hostvars combo — get "
            "comfortable with hostvars[host]['ansible_facts'][...] "
            "specifically.",
        ],
    },
    "file_content": {
        "explanation": (
            "copy/lineinfile manage file content, file manages "
            "directories/permissions/symlinks, and archive/unarchive "
            "(community.general, NOT ansible.builtin) handle tar/zip."
        ),
        "commands": [
            {
                "name": "Exact file content",
                "syntax": "ansible.builtin.copy:\n"
                          "  content: \"Development\\n\"\n"
                          "  dest: /etc/issue",
                "example": "ansible.builtin.copy:\n"
                          "  content: \"Development\\n\"\n"
                          "  dest: /etc/issue",
                "notes": "content: adds no trailing newline unless you "
                         "put one in yourself.",
            },
            {
                "name": "Archive a directory",
                "syntax": "community.general.archive:\n  path: /etc/ssh\n"
                          "  dest: /root/ssh_backup.tar.gz\n  format: gz",
                "example": "community.general.archive:\n  path: /etc/ssh\n"
                          "  dest: /root/ssh_backup.tar.gz\n  format: gz",
                "notes": "In community.general — not preinstalled by "
                         "default, may need an explicit "
                         "ansible-galaxy collection install first.",
            },
        ],
        "common_mistakes": [
            "Assuming community.general is always already installed — "
            "'install the collection if missing' is often an explicit, "
            "graded step, not a given.",
            "Requiring idempotence on an archive of something that "
            "changes constantly (like /var/log) — a second run will "
            "legitimately differ.",
        ],
        "exam_tips": [
            "Compare content exactly, not 'close enough' — a missing or "
            "extra trailing newline is a real, common failure mode here.",
        ],
    },
    "roles": {
        "explanation": (
            "A role is a fixed directory layout (tasks/, handlers/, "
            "templates/, vars/, defaults/) that ansible-galaxy role init "
            "scaffolds for you; roles: under a play applies it by name "
            "(Ansible finds it via roles_path, defaulting to ./roles); "
            "requirements.yml pulls in roles from Galaxy or a URL."
        ),
        "commands": [
            {
                "name": "Scaffold a new role",
                "syntax": "ansible-galaxy role init roles/<name>",
                "example": "ansible-galaxy role init roles/web_role",
                "notes": "",
            },
            {
                "name": "Apply a role",
                "syntax": "- hosts: all\n  roles:\n    - my_role",
                "example": "- hosts: all\n  roles:\n    - my_role",
                "notes": "Just the role NAME, not a path.",
            },
            {
                "name": "External roles via requirements.yml",
                "syntax": "roles:\n  - src: geerlingguy.apache\n"
                          "    name: apache_role\n"
                          "  - src: https://github.com/x/y.git\n"
                          "    name: custom_role",
                "example": "roles:\n  - src: geerlingguy.apache\n"
                          "    name: apache_role\n"
                          "  - src: https://github.com/x/y.git\n"
                          "    name: custom_role",
                "notes": "",
            },
            {
                "name": "Install them",
                "syntax": "ansible-galaxy role install -r "
                          "roles/requirements.yml -p roles",
                "example": "ansible-galaxy role install -r "
                          "roles/requirements.yml -p roles",
                "notes": "-p roles matters — without it, roles install to "
                         "the user's global roles path, not your project.",
            },
        ],
        "common_mistakes": [
            "Forgetting -p roles on install and then wondering why "
            "roles: can't find the role locally.",
            "Assuming role templates/handlers need special syntax — they "
            "reference facts exactly like plain playbooks do.",
        ],
        "exam_tips": [
            "If roles: can't find a role, check roles_path (ansible-config "
            "dump) before assuming the role itself is broken.",
        ],
    },
    "system_roles": {
        "explanation": (
            "RHEL System Roles are Red Hat-certified, pre-built roles for "
            "common sysadmin tasks — timesync, storage, network, "
            "firewall, selinux, logging, kdump, ha_cluster, podman, "
            "postgresql, and more. The catalog has grown to roughly 40+ "
            "roles; don't assume it's just the handful most study guides "
            "mention. Shipped both as the rhel-system-roles RPM and the "
            "redhat.rhel_system_roles collection (upstream mirror: "
            "fedora.linux_system_roles)."
        ),
        "commands": [
            {
                "name": "Install via collection",
                "syntax": "ansible-galaxy collection install "
                          "redhat.rhel_system_roles",
                "example": "ansible-galaxy collection install "
                          "redhat.rhel_system_roles",
                "notes": "",
            },
            {
                "name": "Install via RPM",
                "syntax": "dnf install rhel-system-roles",
                "example": "dnf install rhel-system-roles",
                "notes": "",
            },
            {
                "name": "Use one",
                "syntax": "- hosts: all\n  roles:\n"
                          "    - redhat.rhel_system_roles.timesync\n"
                          "  vars:\n    timesync_ntp_servers:\n"
                          "      - hostname: time.cloudflare.com\n"
                          "        iburst: true",
                "example": "- hosts: all\n  roles:\n"
                          "    - redhat.rhel_system_roles.timesync\n"
                          "  vars:\n    timesync_ntp_servers:\n"
                          "      - hostname: time.cloudflare.com\n"
                          "        iburst: true",
                "notes": "",
            },
            {
                "name": "Find a role's own docs locally",
                "syntax": "ls /usr/share/doc/rhel-system-roles/",
                "example": "cat /usr/share/doc/rhel-system-roles/"
                          "timesync/README.md",
                "notes": "",
            },
        ],
        "common_mistakes": [
            "Using the bare role name (timesync) when it's installed as a "
            "collection, not the RPM — the collection form always needs "
            "the redhat.rhel_system_roles. namespace prefix.",
            "Assuming the role catalog is just the 5-6 famous ones from "
            "older study material — many more exist now.",
        ],
        "exam_tips": [
            "Whichever system role a task names, its variables follow a "
            "predictable <role>_<setting> pattern — check "
            "defaults/main.yml under the role's collection path if unsure "
            "of an exact variable name.",
        ],
    },
    "collections": {
        "explanation": (
            "Content Collections package modules/roles/plugins together. "
            "Version pinning and signature verification are current best "
            "practice for reproducible, supply-chain-safe installs, not "
            "just an advanced edge case."
        ),
        "commands": [
            {
                "name": "requirements.yml",
                "syntax": "collections:\n  - name: ansible.posix\n"
                          "  - name: community.general\n"
                          "    version: '==9.0.0'",
                "example": "collections:\n  - name: ansible.posix\n"
                          "  - name: community.general\n"
                          "    version: '==9.0.0'",
                "notes": "Pin exact versions for anything you actually "
                         "depend on — open-ended >= ranges break "
                         "reproducibility silently when a collection "
                         "updates.",
            },
            {
                "name": "Install to a project-local path",
                "syntax": "ansible-galaxy collection install -r "
                          "collections/requirements.yml -p collections",
                "example": "ansible-galaxy collection install -r "
                          "collections/requirements.yml -p collections",
                "notes": "Pair with collections_path = ./collections in "
                         "[defaults] so Ansible actually looks there.",
            },
            {
                "name": "Verify signatures",
                "syntax": "ansible-galaxy collection verify -r "
                          "collections/requirements.yml --keyring "
                          "~/.ansible/pubring.kbx",
                "example": "ansible-galaxy collection verify -r "
                          "collections/requirements.yml --keyring "
                          "~/.ansible/pubring.kbx",
                "notes": "Part of the current supply-chain-hardening "
                         "tooling (ties into ansible-sign).",
            },
        ],
        "common_mistakes": [
            "Installing to the default user path (~/.ansible/collections) "
            "when the task wants a project-local ./collections directory "
            "— both -p and collections_path matter together.",
            "Committing the installed collections/ directory to git — "
            "only requirements.yml should be tracked.",
        ],
        "exam_tips": [
            "collections_path in ansible.cfg is what makes Ansible "
            "actually find collections installed to a non-default "
            "location — installing them there isn't enough by itself.",
        ],
    },
    "vault": {
        "explanation": (
            "Vault encrypts files or single strings at rest. The classic "
            "single flat --vault-password-file/--ask-vault-pass pattern "
            "still works, but multiple labeled vault IDs "
            "(--vault-id label@source, or vault_identity_list in "
            "ansible.cfg) are now the mainstream pattern once a project "
            "has more than one secret or environment (dev vs prod)."
        ),
        "commands": [
            {
                "name": "Create an encrypted file",
                "syntax": "ansible-vault create --vault-password-file "
                          "secret.txt vault.yml",
                "example": "ansible-vault create --vault-password-file "
                          "secret.txt vault.yml",
                "notes": "",
            },
            {
                "name": "View it",
                "syntax": "ansible-vault view --vault-password-file "
                          "secret.txt vault.yml",
                "example": "ansible-vault view --vault-password-file "
                          "secret.txt vault.yml",
                "notes": "Proves both that the password is right AND that "
                         "the file is genuinely vault-encrypted — a good "
                         "one-command sanity check.",
            },
            {
                "name": "Encrypt a single variable inline",
                "syntax": "ansible-vault encrypt_string "
                          "--vault-password-file secret.txt 'S3cret!' "
                          "--name db_password",
                "example": "ansible-vault encrypt_string "
                          "--vault-password-file secret.txt 'S3cret!' "
                          "--name db_password",
                "notes": "",
            },
            {
                "name": "Multiple vault IDs (current mainstream pattern)",
                "syntax": "ansible-vault encrypt --vault-id "
                          "dev@dev_pass.txt dev_secrets.yml\n"
                          "ansible-playbook --vault-id dev@dev_pass.txt "
                          "--vault-id prod@prod_pass.txt site.yml",
                "example": "ansible-vault encrypt --vault-id "
                          "dev@dev_pass.txt dev_secrets.yml\n"
                          "ansible-playbook --vault-id dev@dev_pass.txt "
                          "--vault-id prod@prod_pass.txt site.yml",
                "notes": "The label (dev, prod) is a hint to which "
                         "password decrypts which file — not a security "
                         "boundary by itself.",
            },
        ],
        "common_mistakes": [
            "Putting a raw plaintext password directly in password: — "
            "always pipe it through | password_hash('sha512') first, or "
            "the playbook 'succeeds' but login is actually broken.",
            "Mixing whole-file encrypt and single-variable encrypt_string "
            "inconsistently across a project, making it unclear at a "
            "glance what's protected.",
        ],
        "exam_tips": [
            "ansible-vault view is the fastest way to confirm your setup "
            "before wiring the vault file into a playbook with vars_files.",
        ],
    },
    "storage_auto": {
        "explanation": (
            "LVM automation lives in community.general (lvg, lvol) — NOT "
            "ansible.builtin, a very common wrong guess. "
            "ansible_facts['lvm'] exposes existing VG/LV state (gathered "
            "as strings — cast before comparing). The mount module "
            "(ansible.posix) with state: mounted both mounts something "
            "now AND writes /etc/fstab for persistence, which Red Hat's "
            "performance exams explicitly require."
        ),
        "commands": [
            {
                "name": "Create a logical volume",
                "syntax": "community.general.lvol:\n  vg: research\n"
                          "  lv: data\n  size: 1500m",
                "example": "community.general.lvol:\n  vg: research\n"
                          "  lv: data\n  size: 1500m",
                "notes": "",
            },
            {
                "name": "Check existing volume groups first",
                "syntax": "{{ ansible_facts['lvm']['vgs'] }}",
                "example": "when: \"'research' in "
                          "ansible_facts['lvm']['vgs']\"",
                "notes": "Sizes in this fact come back as strings — cast "
                         "with | int or | float before comparing.",
            },
            {
                "name": "Persistent mount",
                "syntax": "ansible.posix.mount:\n  path: /mnt/simcache\n"
                          "  src: tmpfs\n  fstype: tmpfs\n"
                          "  opts: size=256m\n  state: mounted",
                "example": "ansible.posix.mount:\n  path: /mnt/simcache\n"
                          "  src: tmpfs\n  fstype: tmpfs\n"
                          "  opts: size=256m\n  state: mounted",
                "notes": "state: mounted both mounts it now and writes "
                         "the fstab line; state: present only does the "
                         "fstab half, so a right-now check like findmnt "
                         "would fail even with a correct fstab entry.",
            },
            {
                "name": "Whole chain: blank disk -> mounted filesystem",
                "syntax": "- community.general.parted:\n    device: /dev/sdb\n"
                          "    number: 1\n    state: present\n"
                          "    label: gpt\n    part_end: 1GiB\n\n"
                          "- community.general.lvg:\n    vg: data_vg\n"
                          "    pvs: /dev/sdb1\n\n"
                          "- community.general.lvol:\n    vg: data_vg\n"
                          "    lv: data_lv\n    size: 800m\n\n"
                          "- community.general.filesystem:\n    fstype: ext4\n"
                          "    dev: /dev/data_vg/data_lv\n\n"
                          "- ansible.posix.mount:\n    path: /data\n"
                          "    src: /dev/data_vg/data_lv\n    fstype: ext4\n"
                          "    state: mounted",
                "example": "- community.general.parted:\n    device: /dev/sdb\n"
                           "    number: 1\n    state: present\n"
                           "    label: gpt\n    part_end: 1GiB\n\n"
                           "- community.general.lvg:\n    vg: data_vg\n"
                           "    pvs: /dev/sdb1\n\n"
                           "- community.general.lvol:\n    vg: data_vg\n"
                           "    lv: data_lv\n    size: 800m\n\n"
                           "- community.general.filesystem:\n    fstype: ext4\n"
                           "    dev: /dev/data_vg/data_lv\n\n"
                           "- ansible.posix.mount:\n    path: /data\n"
                           "    src: /dev/data_vg/data_lv\n    fstype: ext4\n"
                           "    state: mounted",
                "notes": "Five modules across two collections, in this "
                         "order. lvg creates the physical volume for you — "
                         "there is no separate pvcreate module. parted is "
                         "community.general, NOT ansible.builtin.",
            },
            {
                "name": "Act only on hosts that have the disk",
                "syntax": "- block:\n    - community.general.parted: ...\n"
                          "  when: \"'sdb' in ansible_facts['devices']\"",
                "example": "- block:\n    - community.general.parted: ...\n"
                           "  when: \"'sdb' in ansible_facts['devices']\"",
                "notes": "ansible_facts['devices'] is keyed by SHORT name "
                         "('sdb'), not the full /dev path. Putting the when: "
                         "on a block applies it to every task inside, so you "
                         "write the condition once.",
            },
        ],
        "common_mistakes": [
            "Reaching for ansible.builtin for LVM modules — they live in "
            "community.general.",
            "Using state: present on the mount module when the task wants "
            "the filesystem actually mounted right now, not just recorded "
            "in fstab.",
            "Hard-coding hosts: the-one-with-the-disk instead of gating on "
            "a device fact — the end state may look right, but the task "
            "asked you to DETECT the disk and it's marked wrong.",
            "Looking for '/dev/sdb' as a key in ansible_facts['devices'] — "
            "the keys are bare device names like 'sdb'.",
        ],
        "exam_tips": [
            "'Never fail' storage tasks (create at requested size, fall "
            "back smaller if needed, or report the VG doesn't exist) are "
            "a defensive-coding classic — block/rescue or a when: chain "
            "covering every outcome, and actually test the case where the "
            "VG genuinely doesn't exist.",
        ],
    },
    "users_auto": {
        "explanation": (
            "user/group modules automate account management; append: true "
            "is critical whenever you're adding supplementary groups — "
            "without it, groups: REPLACES a user's entire supplementary "
            "group list instead of adding to it."
        ),
        "commands": [
            {
                "name": "User with a supplementary group",
                "syntax": "ansible.builtin.user:\n  name: amr\n"
                          "  groups: developer_group\n  append: true\n"
                          "  shell: /bin/bash",
                "example": "ansible.builtin.user:\n  name: amr\n"
                          "  groups: developer_group\n  append: true\n"
                          "  shell: /bin/bash",
                "notes": "append: true ADDS to existing groups; leaving "
                         "it out REPLACES all of them.",
            },
            {
                "name": "Group first",
                "syntax": "ansible.builtin.group:\n"
                          "  name: developer_group\n  gid: 3500",
                "example": "ansible.builtin.group:\n"
                          "  name: developer_group\n  gid: 3500",
                "notes": "Create the group before the user references it.",
            },
            {
                "name": "Data-driven, conditional creation",
                "syntax": "loop: \"{{ users }}\"\n"
                          "when: item.job == 'developer'",
                "example": "loop: \"{{ users }}\"\n"
                          "when: item.job == 'developer'",
                "notes": "",
            },
        ],
        "common_mistakes": [
            "groups: without append: true, silently evicting a user from "
            "every other group they belonged to.",
            "Only checking the user WAS created and forgetting to verify "
            "users who shouldn't be created actually weren't.",
        ],
        "exam_tips": [
            "'Users whose job is X must NOT be created' tasks grade on "
            "absence, not just presence — verify with id <user> EXPECTING "
            "failure, don't just skip the creation task and assume that's "
            "enough.",
        ],
    },
    "scheduling_auto": {
        "explanation": (
            "The cron module manages a user's crontab entries; name: is "
            "the idempotence key — re-running with the same name updates "
            "the existing entry instead of duplicating it."
        ),
        "commands": [
            {
                "name": "Recurring job",
                "syntax": "ansible.builtin.cron:\n"
                          "  name: \"heartbeat log\"\n  user: natasha\n"
                          "  minute: \"*/5\"\n  job: 'logger \"heartbeat\"'",
                "example": "ansible.builtin.cron:\n"
                          "  name: \"heartbeat log\"\n  user: natasha\n"
                          "  minute: \"*/5\"\n  job: 'logger \"heartbeat\"'",
                "notes": "",
            },
            {
                "name": "Remove an entry",
                "syntax": "ansible.builtin.cron:\n"
                          "  name: \"heartbeat log\"\n  user: natasha\n"
                          "  state: absent",
                "example": "ansible.builtin.cron:\n"
                          "  name: \"heartbeat log\"\n  user: natasha\n"
                          "  state: absent",
                "notes": "Matched by name:, same as creation.",
            },
            {
                "name": "Scheduled backup — cron runs SHELL, not Ansible",
                "syntax": "ansible.builtin.cron:\n"
                          "  name: \"nightly config backup\"\n  user: root\n"
                          "  minute: \"0\"\n  hour: \"2\"\n"
                          "  job: \"tar -czf /backup/config.tar.gz /etc/ssh\"",
                "example": "ansible.builtin.cron:\n"
                           "  name: \"nightly config backup\"\n  user: root\n"
                           "  minute: \"0\"\n  hour: \"2\"\n"
                           "  job: \"tar -czf /backup/config.tar.gz /etc/ssh\"",
                "notes": "job: is a shell command line. You CANNOT put "
                         "community.general.archive (or any module) in "
                         "there — cron has no idea what Ansible is. Use the "
                         "archive module when ANSIBLE does the archiving; "
                         "use tar when CRON does.",
            },
            {
                "name": "Verify",
                "syntax": "crontab -l -u <user>",
                "example": "crontab -l -u natasha",
                "notes": "",
            },
        ],
        "common_mistakes": [
            "Omitting name: — it IS the idempotence key; without it, "
            "re-running can create duplicate entries instead of updating "
            "the existing one.",
            "Scheduling for root when the task explicitly named a "
            "specific user's crontab.",
            "Trying to schedule an Ansible module as the cron job. The job "
            "is a shell command; reach for tar, not "
            "community.general.archive.",
            "Scheduling a backup into a directory the playbook never "
            "created — the cron line is perfect and the job fails nightly.",
        ],
        "exam_tips": [
            "Always verify with crontab -l -u <user> after the playbook "
            "'succeeds' — a task can report success while having written "
            "to the wrong user's crontab entirely.",
            "Run the scheduled command by hand once. Graders do, and a job "
            "that's scheduled correctly but errors on execution earns "
            "nothing.",
        ],
    },
}
