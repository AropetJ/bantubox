 # Linux Module for Python

This module provides a set of system call wrappers for Linux, allowing Python programs to interact with the Linux kernel directly. These wrappers are missing from the standard Python `os` module, but are essential for implementing various aspects of process containment.

## Installation

To install the `linux` module, simply clone this repository and run the following command:

```
python setup.py install
```

## Usage

Once installed, you can import the `linux` module in your Python scripts and use its functions to perform various system calls. For example, the following code snippet shows how to use the `pivot_root()` function to change the root filesystem of the current process:

```python
import linux

linux.pivot_root("/new/root", "/old/root")
```

This will change the root filesystem of the current process to `/new/root`, and move the current root filesystem to `/old/root`.

## Functions

The `linux` module provides the following functions:

- `pivot_root(new_root, put_old)`: Change the root filesystem of the current process.
- `unshare(flags)`: Disassociate parts of the process execution context.
- `setns(fd, nstype)`: Reassociate process with a namespace.
- `clone(callback, flags, callback_args)`: Create a child process.
- `sethostname(hostname)`: Set the system hostname.
- `mount(source, target, filesystemtype, mountflags, mountopts)`: Mount a filesystem.
- `umount(target)`: Unmount a filesystem.
- `umount2(target, flags)`: Unmount a filesystem with additional flags.

## Constants

The `linux` module also provides the following constants:

- `CLONE_NEWNS`: Unshare the mount namespace.
- `CLONE_NEWUTS`: Unshare the UTS namespace (hostname, domainname, etc).
- `CLONE_NEWNET`: Unshare the network namespace.
- `CLONE_NEWPID`: Unshare the PID namespace.
- `CLONE_NEWUSER`: Unshare the users namespace.
- `CLONE_NEWIPC`: Unshare the IPC namespace.
- `CLONE_THREAD`: Create a new thread.
- `MS_RDONLY`: Mount read-only.
- `MS_NOSUID`: Ignore suid and
