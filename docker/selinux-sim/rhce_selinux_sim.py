"""Make libsemanage-backed SELinux tooling usable on a container node.

WHAT THIS IS NOT: a fake SELinux. Almost everything here is real. The
Docker lab installs selinux-policy-targeted, so the node has the genuine
targeted policy store — all 300-odd real booleans, real port types, real
file contexts — and libsemanage manipulates it for real. A wrong boolean
name still fails with "Boolean x is not defined", straight from policy.

WHAT IS SIMULATED: exactly one thing — the running kernel. SELinux
enforcement lives in the host kernel and containers share it, so a
container never gets its own selinuxfs no matter how it's configured.
Every SELinux tool starts by asking the kernel "are you there?", gets no,
and refuses to do anything at all — including the parts that only ever
touch files on disk.

So this patches the three call sites that need a kernel, and leaves the
rest alone:

  is_selinux_enabled()          -> 1, so tooling proceeds past the gate
  security_getenforce()         -> whatever /etc/selinux/config asks for,
                                   so the mode task grades against the
                                   candidate's own change rather than a
                                   hardcoded answer
  security_get_boolean_active() -> read the POLICY STORE instead of the
                                   kernel; on a real host these agree
                                   after a persistent change, which is
                                   what the tasks ask for
  semanage_bool_set_active()    -> no-op success; there is no kernel
                                   boolean to flip, and the persistent
                                   (on-disk) half already happened

Consequence, stated plainly because a green check must not imply more
than it earned: this grades that you invoked the right tooling with
arguments real policy accepts, and that the resulting on-disk state is
right. It cannot grade enforcement — no denials, no relabel effects,
nothing for audit2allow to chew on. Point RHCE_SIM_NODES at the VM lab
when you want that.

Installed via a .pth so it applies to every interpreter on the node
without the candidate's playbooks having to know it exists.
"""

POLICY_CONFIG = "/etc/selinux/config"
STORE_BOOLEANS = "/var/lib/selinux/{policy}/active/booleans.local"

_ENFORCE = {"enforcing": 1, "permissive": 0, "disabled": 0}


def _config_value(key, default):
    """Read a KEY=value out of /etc/selinux/config."""
    try:
        with open(POLICY_CONFIG) as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                if name.strip().upper() == key:
                    return value.strip().strip('"')
    except OSError:
        pass
    return default


def _getenforce():
    """The mode the candidate's own /etc/selinux/config asks for.

    Deliberately NOT hardcoded to 1: the selinux_mode task grades whether
    the candidate set enforcing, so this has to be able to say no.
    """
    return _ENFORCE.get(_config_value("SELINUX", "enforcing").lower(), 1)


def _boolean_active(name):
    """Boolean value from the on-disk store, standing in for the kernel.

    Checks the local customisations first (what `semanage boolean -m`
    writes and what "persistent" means), then falls back to the policy's
    compiled-in default so untouched booleans read correctly.
    """
    policy = _config_value("SELINUXTYPE", "targeted")
    try:
        with open(STORE_BOOLEANS.format(policy=policy)) as fh:
            for line in fh:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                if key.strip() == name:
                    return int(value.strip())
    except (OSError, ValueError):
        pass
    # Not customised — ask the policy itself for its default. Imported
    # lazily: this module loads on EVERY interpreter start via the .pth,
    # and seobject is far too heavy to pull in unconditionally.
    try:
        import seobject
        records = seobject.booleanRecords()
        records.start()
        entry = records.get_all().get(name)
        records.finish()
        if entry:
            return int(entry[-1])
    except Exception:
        pass
    return 0


def _install():
    try:
        import selinux
    except ImportError:
        return
    selinux.is_selinux_enabled = lambda: 1
    selinux.is_selinux_mls_enabled = lambda: 0
    selinux.security_getenforce = _getenforce
    selinux.selinux_getenforcemode = lambda: (0, _getenforce())
    selinux.security_get_boolean_active = _boolean_active
    selinux.security_set_boolean = lambda name, value: 0
    # setenforce(2) against a kernel that isn't listening. The on-disk
    # half of a mode change (/etc/selinux/config) is a plain file edit and
    # still happens for real.
    selinux.security_setenforce = lambda value: 0

    try:
        import semanage
    except ImportError:
        return
    # Pushing a boolean into the RUNNING policy. Its persistent sibling,
    # semanage_bool_modify_local(), is left completely alone — that one
    # writes the store, which is the half we can and do grade.
    semanage.semanage_bool_set_active = lambda handle, key, sebool: 0


_install()
