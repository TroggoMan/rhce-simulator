#!/usr/bin/env python3
"""
RHCE EX294 (RHEL 10) Exam Simulator — main entry point.

Sibling project to rhcsa-simulator. Presents exam-style Ansible automation
tasks, then grades them by running the candidate's own playbooks against
their own inventory and checking the resulting state on managed nodes.

Usage:
    python3 rhce_simulator.py --setup             # first time? guided, read-only bootstrap check
    python3 rhce_simulator.py --quick             # 5 random tasks
    python3 rhce_simulator.py --exam              # full exam (settings.EXAM_TASK_COUNT tasks)
    python3 rhce_simulator.py --practice roles    # drill one category
    python3 rhce_simulator.py --focus             # practice session weighted to your weakest categories
    python3 rhce_simulator.py --adaptive          # spaced repetition: whatever SM-2 says is due
    python3 rhce_simulator.py --list-tasks        # catalog overview
    python3 rhce_simulator.py --learn             # browse domains -> topics -> study content
    python3 rhce_simulator.py --history           # past sessions
    python3 rhce_simulator.py --reset-progress    # clear tracked history (asks to confirm)

Environment:
    RHCE_SIM_WORKDIR      Ansible working dir (default ~/ansible)
    RHCE_SIM_NODES        comma-separated managed nodes (auto-detected from
                          a running docker/vagrant lab, else localhost)
    RHCE_SIM_REMOTE_USER  remote user for task wording (default devops)
"""

import argparse
import sys

from config import settings
from config.settings import C
from utils import formatters as fmt


def cmd_list_tasks():
    from core.registry import TaskRegistry
    print(fmt.banner(f"{settings.EXAM_NAME} — task catalog"))
    total = 0
    for cat in TaskRegistry.get_all_categories():
        classes = TaskRegistry.get_tasks_by_category(cat)
        total += len(classes)
        domain = settings.CATEGORY_TO_DOMAIN.get(cat, 0)
        print(f"{C.BOLD}{settings.CATEGORY_DISPLAY.get(cat, cat)}{C.RESET} "
              f"{fmt.dim(f'(domain {domain}, {len(classes)} tasks)')}")
        for tc in classes:
            inst = tc().generate()
            first_line = inst.description.strip().splitlines()[0]
            print(f"    {inst.id:<24} {inst.difficulty:<7} {first_line[:70]}")
    print(f"\n{C.BOLD}Total: {total} tasks{C.RESET}")


def cmd_learn():  # pragma: no cover - interactive loop
    from core import learn
    learn.run()


def cmd_history():
    from core.results_db import ResultsDB
    db = ResultsDB()
    rows = db.history()
    print(fmt.banner("Session history"))
    if not rows:
        print("No completed sessions yet.")
    for sid, mode, started, score, max_score in rows:
        pct = round(100 * score / max_score) if max_score else 0
        print(f"  #{sid:<4} {mode:<9} {started}  {score}/{max_score} ({pct}%)")
    stats = db.category_stats()
    if stats:
        print(f"\n{C.BOLD}Per-category pass rate:{C.RESET}")
        for cat, attempts, passes in stats:
            display = settings.CATEGORY_DISPLAY.get(cat, cat)
            print(f"  {display:<38} {passes or 0}/{attempts}")
    db.close()


def _resolve_inventory_path(workdir):
    """The candidate can name their inventory file anything (inventory,
    inventory.ini, hosts.yml, ...) as long as ansible.cfg's own
    [defaults] inventory= setting points at it — the real exam allows
    the same flexibility, and this simulator shouldn't hardcode one
    filename and call anything else 'missing'. Reads that setting back
    when ansible.cfg exists; otherwise falls back to the conventional
    names, in the order most candidates reach for them."""
    cfg = workdir / "ansible.cfg"
    if cfg.is_file():
        try:
            text = cfg.read_text()
        except OSError:
            text = ""
        for line in text.splitlines():
            line = line.split("#", 1)[0].split(";", 1)[0].strip()
            key, sep, value = line.partition("=")
            if sep and key.strip() == "inventory" and value.strip():
                return (workdir / value.strip()).expanduser()
    for candidate in ("inventory", "inventory.ini", "inventory.yml"):
        path = workdir / candidate
        if path.exists():
            return path
    return workdir / "inventory"


def warn_if_no_inventory(category: str = None):
    """The lab scripts deliberately hand you bootstrap-only access (root +
    password), not a working inventory — see scripts/lab-setup.sh and
    scripts/vm-lab-setup.sh. Nothing else in this simulator can run until
    the candidate has built their own, so say so plainly the moment it's
    missing rather than let every task in the session fail silently
    against a broken/absent config with no explanation."""
    inv = _resolve_inventory_path(settings.get_workdir())
    if inv.exists():
        return
    if category in ("ansible_config", "inventory", "managed_nodes"):
        return  # that's precisely what this session is about to practice
    print(fmt.warn(f"No inventory found at {inv}."))
    print(fmt.dim(
        "  This simulator never writes one for you — building your own "
        "inventory, ansible.cfg, automation user and SSH key from "
        "bootstrap (root/password) access is task 1, exactly like the "
        "real exam. Every other task in this session will fail its "
        "execution/state checks without one.\n"
        "  python3 rhce_simulator.py --learn            (Configuring managed nodes)\n"
        "  python3 rhce_simulator.py --practice ansible_config\n"
        "  python3 rhce_simulator.py --practice inventory\n"
        "  python3 rhce_simulator.py --practice managed_nodes\n"))


def cmd_session(mode: str, category: str = None, gui: bool = True,
               gui_port: int = None, gui_bind: str = "0.0.0.0"):
    from core.engine import Session
    from core.registry import TaskRegistry
    if category and category not in TaskRegistry.get_all_categories():
        cats = ", ".join(TaskRegistry.get_all_categories())
        print(fmt.fail(f"Unknown category '{category}'. Available: {cats}"))
        return 1
    warn_if_no_inventory(category)
    Session(mode, category=category, gui=gui, gui_port=gui_port,
           gui_bind=gui_bind).run()
    return 0


def cmd_adaptive(weak_count: int = 4, gui: bool = True, gui_port: int = None,
                 gui_bind: str = "0.0.0.0"):
    """Spaced-repetition practice: whatever SM-2 says is due now.

    Different from --focus, which always drills your worst categories.
    This one respects the schedule — a category you aced last week is not
    due yet and is deliberately left out, so you spend the session on
    material that's actually decaying rather than re-proving what you
    already know. When nothing is due, it says so rather than inventing
    work, and points at --focus.
    """
    from core.engine import Session
    from core.registry import TaskRegistry
    from core.results_db import ResultsDB
    db = ResultsDB()
    all_cats = TaskRegistry.get_all_categories()
    due = db.due_categories(all_cats)[:weak_count]
    db.close()
    if not due:
        print(fmt.banner("Adaptive practice"))
        print(fmt.ok("Nothing is due for review — every category you've "
                     "attempted is still inside its interval."))
        print(fmt.dim("  python3 rhce_simulator.py --focus     drill your "
                      "weakest categories anyway\n"
                      "  python3 rhce_simulator.py --history   see the "
                      "review schedule"))
        return 0
    warn_if_no_inventory()
    print(fmt.banner("Adaptive practice — due for review"))
    for cat in due:
        print(f"  {settings.CATEGORY_DISPLAY.get(cat, cat)}")
    print()
    Session("adaptive", categories=due, gui=gui, gui_port=gui_port,
           gui_bind=gui_bind).run()
    return 0


def cmd_focus(weak_count: int = 4, gui: bool = True, gui_port: int = None,
              gui_bind: str = "0.0.0.0"):
    """A practice session drawn from the candidate's own weakest
    categories — never-attempted categories count as weakest of all."""
    from core.engine import Session
    from core.registry import TaskRegistry
    from core.results_db import ResultsDB
    db = ResultsDB()
    all_cats = TaskRegistry.get_all_categories()
    weakest = db.weak_categories(all_cats)[:weak_count]
    db.close()
    warn_if_no_inventory()
    print(fmt.banner("Focus session — your weakest categories"))
    for cat in weakest:
        print(f"  {settings.CATEGORY_DISPLAY.get(cat, cat)}")
    print()
    Session("focus", categories=weakest, gui=gui, gui_port=gui_port,
           gui_bind=gui_bind).run()
    return 0


def _lab_connection_rows(lab_type: str, nodes: list) -> list:
    """Best-effort, read-only lookup of each detected node's live SSH
    host/port — the same facts lab-setup.sh/vm-lab-setup.sh print once at
    boot and are easy to lose. Docker's ports are fixed by
    docker-compose.yml; Vagrant's are read back via 'vagrant ssh-config'
    since they vary by provider (a real per-VM IP under libvirt, a
    127.0.0.1:NNNN forward under VirtualBox). Never raises — returns []
    on any failure so --setup falls back to its generic guidance."""
    if lab_type == "docker":
        base_port = 2201
        return [(n, "127.0.0.1", 22, base_port + settings._LAB_NODE_NAMES.index(n))
                for n in nodes if n in settings._LAB_NODE_NAMES]

    if lab_type == "vagrant":
        import os
        import subprocess
        vagrant_dir = settings.BASE_DIR / "vagrant"
        rows = []
        for name in nodes:
            try:
                proc = subprocess.run(
                    ["vagrant", "ssh-config", name],
                    capture_output=True, text=True, timeout=5, check=True,
                    cwd=vagrant_dir,
                    env={**os.environ, "VAGRANT_CWD": str(vagrant_dir)},
                )
            except (OSError, subprocess.SubprocessError):
                continue
            host = port = None
            for line in proc.stdout.splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[0] == "HostName":
                    host = parts[1]
                elif len(parts) == 2 and parts[0] == "Port":
                    port = parts[1]
            if host and port:
                rows.append((name, host, 22, int(port)))
        return rows

    return []


def _parse_inventory_hosts(path) -> dict:
    """Minimal read-only INI-inventory reader: returns {hostname: {var:
    value}} for lines that are actual managed-node entries — skips group
    headers, [group:vars]/[group:children] sections (those aren't
    per-host lines), comments and blanks. Best-effort diagnostic aid, not
    a validator — ansible-playbook --syntax-check is what actually
    validates the file elsewhere in this project. Never raises; a file
    that doesn't exist or doesn't parse just yields no hosts."""
    hosts = {}
    in_host_section = True
    try:
        text = path.read_text()
    except OSError:
        return hosts
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].split(";", 1)[0].strip()
        if not line:
            continue
        if line.startswith("["):
            section = line.strip("[]")
            in_host_section = not (section.endswith(":vars") or
                                   section.endswith(":children"))
            continue
        if not in_host_section:
            continue
        parts = line.split()
        name, host_vars = parts[0], {}
        for tok in parts[1:]:
            if "=" in tok:
                k, v = tok.split("=", 1)
                host_vars[k] = v
        hosts.setdefault(name, {}).update(host_vars)
    return hosts


def _diagnose_inventory_against_lab(inv_path, rows: list) -> list:
    """Host-by-host diff between what's actually in the candidate's
    inventory and what the live lab reports (see _lab_connection_rows) —
    turns 'compare these two lists yourself' into a concrete per-host
    verdict and exact fix. Read-only: parses the inventory, never writes
    it. Returns a list of (ok: bool, message) tuples."""
    inv_hosts = _parse_inventory_hosts(inv_path)
    live_by_name = {name: (host, port) for name, host, _dp, port in rows}
    results = []

    for name, host, port in ((n, h, p) for n, h, _dp, p in rows):
        if name not in inv_hosts:
            fix = f"{name} ansible_host={host}"
            if port != 22:
                fix += f" ansible_port={port}"
            results.append((False,
                f"{name} is running ({host}" +
                (f":{port}" if port != 22 else "") +
                f") but isn't in your inventory at all. Add: {fix}"))
            continue
        v = inv_hosts[name]
        ah = v.get("ansible_host")
        if not ah:
            results.append((False,
                f"{name} is in your inventory but has no ansible_host set "
                f"— add ansible_host={host}"))
        elif ah != host:
            results.append((False,
                f"{name}'s ansible_host={ah} doesn't match this lab's "
                f"current address ({host}) — update it"))
        elif port != 22 and str(v.get("ansible_port", "")) != str(port):
            got = v.get("ansible_port")
            results.append((False,
                f"{name}'s ansible_port={got!r} doesn't match ({port}) "
                f"— update it" if got else
                f"{name} is missing ansible_port={port}"))
        else:
            results.append((True, f"{name} — ansible_host/port look correct"))

    for name in inv_hosts:
        if name not in live_by_name:
            results.append((False,
                f"{name} is in your inventory but isn't a node this lab "
                f"has running — typo, stale entry from a different lab, "
                f"or the wrong lab is up. Remove it or check which lab "
                f"you meant to start"))

    return results


def _print_lab_connection_guidance(context: str = "missing", inv_path=None):
    """Detects a running lab (read-only) and shows the candidate live
    host/port values instead of generic placeholder text — or, if
    nothing's running, how to bring one up.

    context="missing": inventory/ansible.cfg don't exist yet — this is
      what step 1 needs to write. context="unreachable": inventory
      exists but ansible -m ping just failed — inv_path gets parsed and
      diffed host-by-host against the live lab, since a stale
      lab-fidelity check (wrong lab running, wrong IP, a node your
      inventory names that this lab doesn't have) looks identical to a
      real bootstrap mistake otherwise. Never writes anything; building
      the inventory itself is still the candidate's own task 1, same as
      the real exam."""
    lab_type, nodes = settings.detect_lab_type_and_nodes()

    if not lab_type:
        if context == "missing":
            print("No lab detected running yet. Bring one up first:")
        else:
            print("No lab detected running right now either — if you "
                  "expected one to be up, that alone explains the "
                  "failure (nothing to answer). Check it didn't stop:")
        print(fmt.dim(
            "\n    ./scripts/bootstrap.sh          pick a lab interactively\n"
            "    ./scripts/lab-setup.sh          Docker — fast, light\n"
            "    ./scripts/vm-lab-setup.sh       VMs — full fidelity, SELinux\n"))
        return

    rows = _lab_connection_rows(lab_type, nodes)
    label = "Docker" if lab_type == "docker" else "VM (Vagrant)"
    if context == "missing":
        print(f"Detected a running {label} lab — here's what step 1 needs, live:")
    elif rows:
        print(f"Detected a running {label} lab. Checking your inventory "
              f"against it, host by host:")
        for ok, message in _diagnose_inventory_against_lab(inv_path, rows):
            print(f"  {fmt.ok(message) if ok else fmt.fail(message)}")
        print()
    if not rows:
        probe = "docker ps" if lab_type == "docker" else "vagrant ssh-config <node>"
        print(fmt.dim(f"  (couldn't read live connection details — run "
                      f"{probe} yourself for host/port.)\n"))
        return

    if context == "missing":
        for name, host, _default_port, port in rows:
            port_note = "" if port == 22 else f"  ansible_port={port}"
            print(f"    {name:<8} ansible_host={host}{port_note}")

        example = "\n".join(
            f"    {name} ansible_host={host}" + ("" if port == 22 else f" ansible_port={port}")
            for name, host, _default_port, port in rows)
        print(fmt.dim(
            f"\n  Example ./inventory for the bootstrap connection ONLY — "
            f"delete ansible_user/ansible_ssh_pass once you've switched to "
            f"your own key in step 4:\n"
            f"    [all]\n{example}\n"
            f"    [all:vars]\n"
            f"    ansible_user=root\n"
            f"    ansible_ssh_pass=<the root password the lab script printed>\n"))

    if lab_type == "docker":
        print(fmt.dim(
            "  Root password defaults to 'rhce-lab' (RHCE_LAB_ROOT_PASSWORD "
            "to override). Alternatively, work from inside the control "
            "container (docker exec -it control bash) and skip "
            "ansible_host/ansible_port entirely — nodes resolve there as "
            "plain hostnames on port 22, closer to what the real exam "
            "hands you.\n"))
    else:
        print(fmt.dim(
            "  Root password defaults to 'rhce-lab' (RHCE_LAB_ROOT_PASSWORD "
            "to override). These addresses are assigned by the VM provider "
            "and can change across 'vagrant reload' or a host reboot — "
            "re-run --setup if connections that used to work start "
            "failing, to confirm they haven't moved.\n"))


def cmd_setup_guide():
    """Optional, read-only walkthrough for first-time bootstrap. It never
    writes a file or changes anything on a managed node — it only checks
    what you've already built and, once inventory + ansible.cfg exist,
    pings your inventory for real feedback (the same 'grade by results'
    approach the rest of the simulator uses). Skip this entirely and just
    write the files by hand if you already know the drill — --quick,
    --exam and --practice never require having run this first."""
    from validators import ansible_runner as runner
    workdir = settings.get_workdir()
    print(fmt.banner("First-time setup guide (optional)"))
    print(fmt.dim(
        "Nothing here writes a file for you or changes anything on a "
        "managed node — it only checks state and, at the end, actually "
        "pings your inventory. If you already know the drill, skip this "
        "and just build the files yourself; --quick/--exam/--practice "
        "work fine without ever running this.\n"))

    def _status(path):
        """A 0-byte file 'exists' but configures nothing — ansible then
        silently falls back to implicit localhost with no hint why, which
        is a far more confusing failure than just saying so now."""
        if not path.exists():
            return False, fmt.fail(f"{path.name} NOT found")
        if path.stat().st_size == 0 or not path.read_text().strip():
            return False, fmt.fail(f"{path.name} exists but is EMPTY — nothing configured yet")
        return True, fmt.ok(f"{path.name} found")

    inv, cfg = _resolve_inventory_path(workdir), workdir / "ansible.cfg"
    inv_ok, inv_status = _status(inv)
    cfg_ok, cfg_status = _status(cfg)
    print(f"Working directory: {workdir}\n")
    print(f"  {inv_status}  ({inv})")
    print(f"  {cfg_status}  ({cfg})")
    print()

    if not inv_ok or not cfg_ok:
        print("Nothing to test yet. On the real exam (and on this lab's "
              "VMs/containers) you start with root, reachable by password "
              "— no inventory, no automation user, no key. Two files and "
              "one bootstrap connection get you the rest of the way:")
        print(fmt.dim(
            "\n  1. Write ./inventory listing each node's SSH host/port.\n"
            "  2. Write ./ansible.cfg pointing at it.\n"
            "  3. Connect ONCE as root with -k (password auth) to create "
            "your own automation user, push an SSH key, and drop a "
            "passwordless-sudo sudoers file.\n"
            "  4. Switch ansible_user/ansible_ssh_private_key_file in the "
            "inventory over to that — no password anywhere after this.\n"))
        _print_lab_connection_guidance()
        if not cfg_ok:
            print(fmt.dim(
                "  Example ./ansible.cfg for step 2 — points at the "
                "inventory above and turns on sudo escalation, nothing "
                "more:\n"
                "    [defaults]\n"
                f"    inventory = ./{inv.name}\n"
                "    remote_user = devops\n"
                "    host_key_checking = False\n\n"
                "    [privilege_escalation]\n"
                "    become = True\n"
                "    become_method = sudo\n"
                "    become_ask_pass = False\n"))
        print("Full syntax, real command examples and the exact -k/-K "
              "bootstrap sequence:")
        print("    python3 rhce_simulator.py --learn            "
              "(then: Configuring managed nodes)")
        print("Graded practice for each piece, once you've written "
              "something to check:")
        print("    python3 rhce_simulator.py --practice ansible_config")
        print("    python3 rhce_simulator.py --practice inventory")
        print("    python3 rhce_simulator.py --practice managed_nodes")
        return 0

    print("Both files exist. Testing the connection for real "
          "(ansible all -m ping)...")
    if not runner.have_ansible():
        print(fmt.warn("ansible-playbook not found on this control node — "
                       "install ansible-core to actually test this."))
        return 0
    out = runner.adhoc("all", "ansible.builtin.ping", workdir=workdir)
    if out.ok and "pong" in out.stdout:
        print(fmt.ok("Every host in your inventory answered ping."))
        print("Bootstrap looks done. Next:")
        print("    python3 rhce_simulator.py --quick")
        print("    python3 rhce_simulator.py --focus     "
              "(weighted to your weakest categories)")
        lab_type, _nodes = settings.detect_lab_type_and_nodes()
        if lab_type == "vagrant":
            print(fmt.dim(
                "\n  Bootstrap only needs doing ONCE, ever, if you snapshot "
                "now: ./scripts/lab-reset.sh --vm --save-snapshot bakes "
                "this bootstrapped state in as the new baseline. Every "
                "reset after that (./scripts/lab-reset.sh --vm) wipes "
                "whatever a practice task left behind — LVM, SELinux, "
                "cron, users — in seconds, while devops/inventory/key stay "
                "intact. Skip this and a reset takes you back to "
                "root/password only, bootstrap included.\n"))
    else:
        print(fmt.fail("Ping failed against at least one host:"))
        for line in out.text.strip().splitlines()[-15:]:
            print(fmt.dim(f"    {line}"))
        print()
        _print_lab_connection_guidance(context="unreachable", inv_path=inv)
        print("Common causes once your inventory names match a node that's "
              "actually running: ansible_user/ansible_ssh_private_key_file "
              "don't match the key you actually pushed, the automation "
              "user's authorized_keys wasn't written, or the bootstrap "
              "playbook never actually ran. --learn managed_nodes walks "
              "the sequence again if you want to retrace it.")
    return 0


def cmd_reset_progress():
    from core.results_db import ResultsDB
    reply = input("This permanently clears all tracked session history and "
                  "category stats. Continue? [y/N] ").strip().lower()
    if reply not in ("y", "yes"):
        print(fmt.dim("Cancelled — nothing was reset."))
        return 0
    db = ResultsDB()
    db.reset()
    db.close()
    print(fmt.ok("Progress history cleared."))
    return 0


SETUP_EPILOG = """\
First time here? Nodes come up with root/password only — no inventory,
no automation user, no key (see the lab script's own printed output).
Building that is your first task, not something this tool does for you:

    python3 rhce_simulator.py --setup     guided, read-only walkthrough:
                                           checks what exists, pings your
                                           inventory once it does — never
                                           writes a file for you
    python3 rhce_simulator.py --learn     full bootstrap syntax, under
                                           "Configuring managed nodes"

Already know the drill? Write ./inventory and ./ansible.cfg yourself and
skip straight to --quick/--exam/--practice — none of them require --setup.
"""


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=f"{settings.EXAM_NAME} exam simulator v{settings.VERSION}",
        epilog=SETUP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--quick", action="store_true", help="5 random tasks")
    group.add_argument("--exam", action="store_true",
                       help=f"full exam ({settings.EXAM_TASK_COUNT} tasks)")
    group.add_argument("--practice", metavar="CATEGORY",
                       help="drill a single category")
    group.add_argument("--focus", action="store_true",
                       help="practice session weighted to your weakest categories")
    group.add_argument("--adaptive", action="store_true",
                       help="spaced-repetition session: categories SM-2 says "
                            "are due for review")
    group.add_argument("--setup", action="store_true",
                       help="optional guided first-time bootstrap check "
                            "(read-only — checks state, pings once ready; "
                            "never writes a file for you)")
    group.add_argument("--list-tasks", action="store_true",
                       help="show the task catalog")
    group.add_argument("--learn", action="store_true",
                       help="show EX294 objectives")
    group.add_argument("--history", action="store_true",
                       help="show past session results")
    group.add_argument("--reset-progress", action="store_true",
                       help="clear tracked session history (asks to confirm)")
    # The task panel is ON by default: real exams put their questions in a
    # window of their own, so practising that split (question sheet in one
    # window, terminal work in another) is the honest default here too.
    # We serve ours to a browser; Red Hat's is a native app — the window is
    # the point, not the technology. --no-gui opts out. Both flags write the
    # same dest, so whichever comes last wins.
    from core.task_gui import DEFAULT_PORT as GUI_PORT
    parser.add_argument("--gui", nargs="?", const=GUI_PORT, type=int,
                       default=GUI_PORT, metavar="PORT",
                       help=f"port for the task panel (default {GUI_PORT}). "
                            f"On by default; pass a port only to move it.")
    parser.add_argument("--no-gui", dest="gui", action="store_const", const=None,
                       help="run in the terminal only, with no task panel")
    parser.add_argument("--gui-bind", default="0.0.0.0", metavar="ADDR",
                       help="address the task panel listens on (default "
                            "0.0.0.0, so a headless control node can be read "
                            "from your laptop; use 127.0.0.1 to keep it local)")
    args = parser.parse_args(argv)
    gui_enabled = args.gui is not None
    gui_kwargs = dict(gui=gui_enabled, gui_port=args.gui, gui_bind=args.gui_bind)

    if args.list_tasks:
        cmd_list_tasks()
    elif args.learn:
        cmd_learn()
    elif args.history:
        cmd_history()
    elif args.reset_progress:
        return cmd_reset_progress()
    elif args.setup:
        return cmd_setup_guide()
    elif args.quick:
        return cmd_session("quick", **gui_kwargs)
    elif args.exam:
        return cmd_session("exam", **gui_kwargs)
    elif args.practice:
        return cmd_session("practice", category=args.practice, **gui_kwargs)
    elif args.focus:
        return cmd_focus(**gui_kwargs)
    elif args.adaptive:
        return cmd_adaptive(**gui_kwargs)
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
