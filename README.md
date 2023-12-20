
## Title - BantuBox

## Introduction
BantuBox is a simplified and educational exploration of containerization technology, presenting a user-friendly alternative to Docker. Developed entirely in Python, the implementation leverages kernel Namespaces, cgroups, and network namespaces specific to Linux. To overcome the limitations of the python os module for Linux system calls, we enhance functionality by creating wrappers using the C language, which are then imported as modules in our project. The project's focus is not to replicate Docker comprehensively but rather to establish a foundational model that adequately elucidates the fundamental principles of container technology.


## Features

- Process isolation and containment
- Creation and management of Linux containers
- Mounting and management of file systems within containers
- Use of Python and C for Linux system call wrappers



## Installation

To install BantuBox, follow these steps:

```bash
  git clone <Repository URL>
  cd bantubox/app
  chmod +x bb.py
```


## Environment and setup

```bash
# Creating a virtual python3 environment
python3 -m venv bb3venv

# Activate the environment
source bb3venv/bin/activate

# Install other required packages in the requirements.txt file
sudo pip3 install -r requirements.txt

# Installing the linux module
setup.py file is already provided
sudo python setup.py bdist_wheel
sudo pip install dist/your_module_name-1.0-cp3x-cp3x-linux_x86_64.whl # replace the filename with the actual name of your wheel file

# Creating an image directory
sudo apt-get install debootstrap # Install debootstrap
mkdir /bantubox/images/ubuntu # Create a target directory for your minimal Ubuntu installation
sudo debootstrap --variant=minbase focal /bantubox/images/ubuntu # Run debootstrap to install the base system, replace focal with any ubuntu image you want
sudo chroot /bantubox/images/ubuntu # Chroot into the minimal system and add additional packages you want then exit
sudo tar -cvf ubuntu.tar -C /bantubox/container/ubuntu # Create a tarball

# Creating a container directory
mkdir containers

# Mount the bantubox cpu cgroup
# Note: The program automatically creates the cgroup bantubox
sudo mount -t tmpfs none /sys/fs/cgroup/cpu/bantubox

```

## Examples and Usage

```bash
# Then run a command in a terminal window:
sudo ./bb.py run <command> <options>

# For example:
sudo ./bb.py run -i ubuntu /bin/bash

# Other commands in the future will include:
stop to stop a running container
list to list available containers
delete to delete a container by id
```


## Strategy

We will want bantubox to have features closely similar to those from Docker, so I followed the following developmet steps:

1. Practiced the usage of fork and exec system calls
2. Used chroot to jail a process in the container
3. Mounting namespaces to start process isolation
4. Used pivot root to replace chroot as it's more effective
5. To reduce launch speeds, I implemented an overlay filesystem
6. Changed the container's hostname to it's ID using the UTS namespace
7. We then use the unshare sys call to isolate the container and it's processes
8. Followed by enabling networking tools like ps, ifconfig using the net namespace
9. We then implement cgroups for resource utilization control
10. Future features will include stopping and listing of available containers


## Contributing

Contributions to BantuBox are welcome. Please follow these steps to contribute:
- Fork the repository.
- Create a new branch for your feature.
- Commit your changes.
- Push to the branch.
- Submit a pull request.

## Acknowledgements

- ALX for giving me the platform and structure to learn and become a better software engineer.
- My peers and community members for their support and contributions.


## Licensing
This application is free to use for anyone who comes across it
