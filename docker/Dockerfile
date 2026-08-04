# Managed-node image for the rhce-simulator Docker lab.
# Based on Rocky's -ubi-init variant, which is purpose-built to run systemd
# as PID 1 in a container (no manual unit-masking hacks needed) so the
# cron/service/firewalld modules the simulator exercises behave like a real
# RHEL-family host. SELinux enforcement is the exception: that's a host
# kernel feature and can't be made to work in a container regardless of
# base image — see the README's Known limitations section.
FROM rockylinux/rockylinux:10-ubi-init

ARG root_password

# python3-dnf: Rocky/RHEL 10 default to dnf5, whose Python bindings
# (python3-libdnf5) aren't what ansible.builtin.dnf talks to — without the
# legacy python3-dnf compat package that module fails with "No module named
# 'dnf'" on every managed node. Installed so the simulator's existing dnf-
# based tasks work unmodified; task content also points candidates at
# ansible.builtin.package/dnf5 as the more portable current alternative.
# curl: the custom-port web task proves the node actually SERVES content,
#   not merely that it's configured to.
# cronie: ships the unit as crond.service, NOT cronie.service — enabling it
#   under the package's own name fails the build outright.
# tar / parted: used by the scheduled-backup and disk-chain tasks.
# policycoreutils-python-utils + libselinux-utils: the SELinux tasks tell
#   candidates to install semanage tooling themselves, but having getenforce
#   present here means the simulator's SELinux probe gets a clean "disabled"
#   answer instead of "command not found" — so it reports the real reason
#   those checks are skipped. Enforcement itself still cannot work in a
#   container (host-kernel feature); see the README's Known limitations.
# iproute: Ansible's network fact collector shells out to `ip`. The base
#   image doesn't ship it, and without it setup gathers NO network facts at
#   all — silently. ansible_default_ipv4 / ansible_all_ipv4_addresses /
#   ansible_interfaces simply don't appear, so the hosts.j2 template task
#   (which asks for each host's IP out of hostvars) has nothing to render
#   from and fails on a correct answer. VMs get this for free; containers
#   need it stated.
# e2fsprogs: mkfs.ext4, which the storage tasks' filesystem module shells
#   out to. Absent from the base image, so the LVM chain would die at the
#   last step on any node that does have a device to build on.
# selinux-policy-targeted: the actual targeted policy store. This is what
#   makes the SELinux tasks gradeable here rather than simulated — see
#   selinux-sim/rhce_selinux_sim.py. Real booleans, real port types, real
#   file contexts; a wrong name is rejected by real policy, not by us.
RUN dnf -y install openssh-server sudo cronie python3 python3-dnf firewalld \
        lvm2 passwd curl tar parted policycoreutils-python-utils \
        libselinux-utils iproute e2fsprogs selinux-policy-targeted \
    && dnf clean all \
    && systemctl enable sshd crond firewalld \
    && ssh-keygen -A

# Everything SELinux on a container node hinges on one lie — that a kernel
# is listening — and nothing else. See selinux-sim/rhce_selinux_sim.py for
# the full reasoning and for what this consequently cannot grade.
# The .pth makes it load in every interpreter on the node, so the
# candidate's playbooks never have to know it exists. The two CLI
# stand-ins exist because getenforce/getsebool are C binaries the Python
# shim cannot reach; semanage is a Python script and needs no help.
#
# The stand-ins REPLACE the real binaries at their own paths rather than
# shadowing them from /usr/local/sbin. Shadowing depends on PATH order,
# and Ansible's command module runs with a non-login PATH that finds
# /usr/sbin first — so the real getsebool answered and the stand-in never
# ran. Originals are kept alongside as .real for anyone debugging.
COPY selinux-sim/rhce_selinux_sim.py /usr/lib/python3.12/site-packages/
COPY selinux-sim/getenforce selinux-sim/getsebool /usr/local/sbin/
RUN echo "import rhce_selinux_sim" \
        > /usr/lib/python3.12/site-packages/rhce_selinux_sim.pth \
    && for tool in getenforce getsebool; do \
         mv "/usr/sbin/$tool" "/usr/sbin/$tool.real" \
         && install -m 0755 "/usr/local/sbin/$tool" "/usr/sbin/$tool"; \
       done \
    && rm -f /usr/local/sbin/getenforce /usr/local/sbin/getsebool

# LVM normally leans on udev to create its device nodes. There is no udev
# here (running it would process events for every device on the HOST
# kernel), so tell LVM to manage its own nodes instead — without this,
# lvcreate succeeds but /dev/<vg>/<lv> never appears and mkfs/mount fail
# with "Can't lookup blockdev".
RUN mkdir -p /etc/lvm && printf '%s\n' \
        'activation {' \
        '    udev_sync = 0' \
        '    udev_rules = 0' \
        '}' \
        'devices {' \
        '    obtain_device_list_from_udev = 0' \
        '}' > /etc/lvm/lvmlocal.conf

# EXAM-STYLE bootstrap access only — root, reachable by password. No
# automation user, no SSH key baked in: building your own inventory,
# ansible.cfg, automation user, key and sudoers from this bootstrap
# access is the candidate's actual first task, exactly like the real
# exam hands you nodes. See scripts/lab-setup.sh for what gets printed.
#
# A drop-in under sshd_config.d, not an edit to the main sshd_config:
# RHEL-family sshd_config Includes that directory near the TOP of the
# file, and OpenSSH keeps the FIRST value it sees per keyword — any
# later drop-in (or a base-image default) that also sets these loses
# silently to whichever sorts first. Naming ours 00- wins that race
# without needing to know what else might set it.
RUN echo "root:${root_password}" | chpasswd \
    && mkdir -p /etc/ssh/sshd_config.d \
    && printf 'PasswordAuthentication yes\nPermitRootLogin yes\n' \
        > /etc/ssh/sshd_config.d/00-rhce-lab-bootstrap.conf

STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
