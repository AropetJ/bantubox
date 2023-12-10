
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
