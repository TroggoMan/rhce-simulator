# Managed-node image for the rhce-simulator Docker lab.
# Based on Rocky's -ubi-init variant, which is purpose-built to run systemd
# as PID 1 in a container (no manual unit-masking hacks needed) so the
# cron/service/firewalld modules the simulator exercises behave like a real
# RHEL-family host. SELinux enforcement is the exception: that's a host
# kernel feature and can't be made to work in a container regardless of
# base image — see the README's Known limitations section.
FROM rockylinux/rockylinux:10-ubi-init

ARG user

# python3-dnf: Rocky/RHEL 10 default to dnf5, whose Python bindings
# (python3-libdnf5) aren't what ansible.builtin.dnf talks to — without the
# legacy python3-dnf compat package that module fails with "No module named
# 'dnf'" on every managed node. Installed so the simulator's existing dnf-
# based tasks work unmodified; task content also points candidates at
# ansible.builtin.package/dnf5 as the more portable current alternative.
# curl: the custom-port web task proves the node actually SERVES content,
#   not merely that it's configured to.
# tar / parted: used by the scheduled-backup and disk-chain tasks.
# policycoreutils-python-utils + libselinux-utils: the SELinux tasks tell
#   candidates to install semanage tooling themselves, but having getenforce
#   present here means the simulator's SELinux probe gets a clean "disabled"
#   answer instead of "command not found" — so it reports the real reason
#   those checks are skipped. Enforcement itself still cannot work in a
#   container (host-kernel feature); see the README's Known limitations.
RUN dnf -y install openssh-server sudo cronie python3 python3-dnf firewalld \
        lvm2 passwd curl tar parted policycoreutils-python-utils \
        libselinux-utils \
    && dnf clean all \
    && systemctl enable sshd cronie firewalld \
    && ssh-keygen -A

RUN useradd -m "${user}" \
    && echo "${user} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/"${user}" \
    && chmod 440 /etc/sudoers.d/"${user}" \
    && mkdir -p /home/"${user}"/.ssh \
    && chmod 700 /home/"${user}"/.ssh \
    && chown -R "${user}:${user}" /home/"${user}"

STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
