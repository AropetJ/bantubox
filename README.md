
# BantuBox

BantuBox is a simplified Docker-like application for running Linux containers. It allows users to encapsulate processes and run them in isolated environments, similar to how Docker operates.

## Color Reference

| Color             | Hex                                                                |
| ----------------- | ------------------------------------------------------------------ |
| Example Color | #092635 |
| Example Color | #1B4242 |
| Example Color | #5C8374 |
| Example Color | #9EC8B9 |


## Acknowledgements

- ALX for giving me the platform and structure to learn and become a better software engineer.
- My peers and community members for their support and contributions.


## Contributing

Contributions to BantuBox are welcome. Please follow these steps to contribute:
- Fork the repository.
- Create a new branch for your feature.
- Commit your changes.
- Push to the branch.
- Submit a pull request.


## Features

- Process isolation and containment
- Creation and management of Linux containers
- Mounting and management of file systems within containers
- Use of Python and C for Linux system call wrappers



## Installation

To install BantuBox, follow these steps:

```bash
  git clone [Repository URL]
  cd BantuBox
  chmod +x bb.py
```
    
## Usage/Examples

Run a command in a new container:

```bash
sudo ./bb.py run <command> <options>

For example:
sudo ./bb.py run /bin/bash

Other commands in the future will include:

stop to stop a running container
list to list available containers
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
