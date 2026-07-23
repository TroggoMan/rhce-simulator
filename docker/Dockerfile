# Managed-node image for the rhce-simulator Docker lab.
# Based on Rocky's -ubi-init variant, which is purpose-built to run systemd
# as PID 1 in a container (no manual unit-masking hacks needed) so the
# cron/service/firewalld modules the simulator exercises behave like a real
# RHEL-family host. SELinux enforcement is the exception: that's a host
# kernel feature and can't be made to work in a container regardless of
# base image — see the README's Known limitations section.
FROM rockylinux/rockylinux:10-ubi-init

ARG user

RUN dnf -y install openssh-server sudo cronie python3 firewalld lvm2 passwd \
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
