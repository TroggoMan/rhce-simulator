#!/bin/bash
# Disposable Docker-based Ansible lab for use with rhce-simulator.
# Spins up 5 containers (control-style Ubuntu nodes + one Rocky node) on an
# isolated bridge network, wires up ~/.ansible.cfg and an inventory, and
# grants SSH access via a px-access playbook. Adapted from a Red Hat
# training lab script (Alta3/ACG RHCE course).
#
# Point RHCE_SIM_NODES at these hostnames (morty, summer, jerry, beth, rick)
# once the lab is up.

# 1. Dynamically grab the Server's current API version
# This ensures that if the VM updates to 1.54 later, the script updates too.
export DOCKER_API_VERSION=$(docker version -f '{{.Server.APIVersion}}')

### Set ARGS for build up here in case needs used earlier
DOCKERFILE=$HOME/px/dockerfiles/2204/staff

echo $DOCKER_API_VERSION
sleep 1

echo -e "Cleaning up Containers..."
sudo docker stop zim gir dib gaz membrane tak &> /dev/null
sudo docker rm -f zim gir dib gaz membrane tak &> /dev/null
sudo docker network rm ansible-net &> /dev/null
rm /tmp/labrunning &> /dev/null

sudo docker stop morty &> /dev/null
sudo docker rm -f morty &> /dev/null
sudo docker network rm ansible-net &> /dev/null
rm /tmp/labrunning &> /dev/null

sudo docker stop summer jerry beth rick morty &> /dev/null
sudo docker rm -f summer jerry beth rick morty &> /dev/null
sudo docker network rm ansible-net &> /dev/null
rm /tmp/labrunning &> /dev/null
echo -e "Containers Cleared!\n"

echo -e "Assembling the Smith family...\n"

# 2. Define the Helper Function
# This handles the versioning and the build command in one place
build_px_image() {
    local name=$1
    echo "Building image for $name..."
    sudo DOCKER_API_VERSION=$DOCKER_API_VERSION docker build -q \
        --build-arg user="$name" \
        --tag "$name:22.04" \
        "$DOCKERFILE"
}

### Create networks
sudo docker network create --opt com.docker.network.driver.mtu=1450 --subnet 10.10.2.0/24 ansible-net

### Build docker images using the function
# If you ever need to change the build logic, you only change it once in the function!
for member in summer jerry beth morty; do
    build_px_image "$member"
done

### Launch containers and connect networks
sudo docker run -d  --name morty   -h morty   --ip 10.10.2.2 --network ansible-net morty:22.04
sudo docker run -d  --name summer  -h summer  --ip 10.10.2.3 --network ansible-net summer:22.04
sudo docker run -d  --name jerry   -h jerry   --ip 10.10.2.4 --network ansible-net jerry:22.04
sudo docker run -d  --name beth    -h beth    --ip 10.10.2.5 --network ansible-net beth:22.04
sudo docker run -d  --name rick    -h rick    --ip 10.10.2.6 --network ansible-net registry.gitlab.com/alta3/planetexpress/rocky/rocky:9

sudo apt install sshpass -y

# docker version 20.10.25 patch which dockerfile makes home directories root ownership
names=("summer" "jerry" "beth" "morty")
for name in "${names[@]}"; do
    sudo docker exec -it $name chown -R $name:$name /home/$name
done

echo -e ".ansible.cfg Updated (/home/student/.ansible.cfg)"
curl https://static.alta3.com/projects/ansible/deploy/ansiblecfg --create-dirs -o ~/.ansible.cfg

echo -e "Inventory File Updated (/home/student/mycode/inv/dev/hosts)"
curl https://static.alta3.com/projects/ansible/deploy/hosts --create-dirs -o ~/mycode/inv/dev/hosts

echo -e "Nethosts Inventory File Updated (/home/student/mycode/inv/dev/nethosts)"
curl https://static.alta3.com/projects/ansible/deploy/nethosts --create-dirs -o ~/mycode/inv/dev/nethosts

ansible-playbook ~/px/scripts/px-access.yml -i ~/mycode/inv/dev/hosts
