#!/home/aropet/bantubox/bb3venv/bin/python3

"""
BantuBox: A Lightweight Container Management Tool

This script provides functionality similar to Docker, allowing users to create, run,
and manage Linux containers with ease. BantuBox is designed to be simple and
straightforward, making it suitable for both educational purposes and practical usage.

Usage:
  To run a container:
    sudo ./bb.py run --image-name <image_name> --command <command> [options]

  For more information on available options, use:
    sudo ./bb.py --help

Examples:
  sudo ./bb.py run --image-name ubuntu --command /bin/bash
  sudo ./bb.py run --image-name alpine --command /bin/echo 'Hello, World!'
"""

# Global Constants
IMAGE_DIR = '/home/aropet/bantubox/images'
CONTAINER_DIR = '/home/aropet/bantubox/containers'

import os  # File and process management
import shutil
import signal
import stat
import tarfile  # Extracting the image tarball files
import uuid  # Unique container ids

import click  # Command line utility
import linux  # Linux sys call wrappers

def _get_image_path(image_name, image_dir, image_suffix='tar'):
    """
    Construct the full file path for a given container image.

    Args:
    - image_name (str): The name of the image.
    - image_dir (str): The directory where images are stored.
    - image_suffix (str, optional): The file extension for the image, default 'tar'.

    Returns:
    - str: The path to the image file.

    Raises:
    - FileNotFoundError: If the specified image directory does not exist.
    """
    if not os.path.exists(image_dir):
        raise FileNotFoundError(f"Image directory '{image_dir}' does not exist.")

    return os.path.join(image_dir, f"{image_name}.{image_suffix}")


def _get_container_path(container_id, container_dir, *subdir_names):
    """
    Construct a directory path for a created container.

    Args:
    - container_id (str): Unique identifier for the container.
    - container_dir (str): Base directory for storing container data.
    - subdir_names (str): Subdirectories within the container's directory.

    Returns:
    - str: The path to the container's directory.
    
    Raises:
    - FileNotFoundError: If the container base directory does not exist.
    """
    if not os.path.exists(container_dir):
        raise FileNotFoundError(f"Container base directory '{container_dir}' does not exist.")

    return os.path.join(container_dir, container_id, *subdir_names)


def create_container_root(image_name, image_dir, container_id, container_dir):
    """
    Create a root directory for a container and extract the image into it.

    Args:
    - image_name (str): Name of the container image.
    - image_dir (str): Directory where the container images are stored.
    - container_id (str): Unique identifier for the container.
    - container_dir (str): Directory to store container-related files.

    Returns:
    - str: Path to the container's root filesystem.

    Raises:
    - FileNotFoundError: If the image file does not exist.
    - OSError: If directory creation or file extraction fails.
    """
    image_path = _get_image_path(image_name, image_dir)

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Unable to locate image '{image_name}' at '{image_path}'")

    image_root = os.path.join(image_dir, image_name, 'rootfs')

    try:
        if not os.path.exists(image_root):
            os.makedirs(image_root)

            with tarfile.open(image_path) as tar_file:
                filtered_members = [m for m in tar_file.getmembers() if m.type not in (tarfile.CHRTYPE, tarfile.BLKTYPE)]
                tar_file.extractall(image_root, members=filtered_members)
    except OSError as e:
        raise OSError(f"Error creating directory or extracting files: {e}")

    return _setup_container_directories(container_id, container_dir, image_root)

# Helper function for setting up container directories
def _setup_container_directories(container_id, container_dir, image_root):
    """
    Setup directories for container operation such as copy-on-write and mount points.

    Args:
    - container_id (str): Unique identifier for the container.
    - container_dir (str): Base directory for storing container data.
    - image_root (str): Path to the root filesystem of the image.

    Returns:
    - str: Path to the container's root filesystem.
    """
    dirs = {
        'cow_rw': 'cow_rw',
        'cow_workdir': 'cow_workdir',
        'rootfs': 'rootfs'
    }

    for key, subdir in dirs.items():
        dir_path = _get_container_path(container_id, container_dir, subdir)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        dirs[key] = dir_path

    linux.mount(
        'overlay', dirs['rootfs'], 'overlay', linux.MS_NODEV,
        f"lowerdir={image_root},upperdir={dirs['cow_rw']},workdir={dirs['cow_workdir']}")

    return dirs['rootfs']


@click.group()
def cli():
    """
    Command-line interface for managing containers with BantuBox.

    This CLI provides commands for running, stopping, listing, and deleting containers.
    """
    pass


def makedev(dev_path):
    """
    Create device identifiers and special files in the container's /dev directory.

    Args:
    - dev_path (str): The path to the container's /dev directory.

    Raises:
    - OSError: If symlink or device creation fails.
    """
    std_fds = ['stdin', 'stdout', 'stderr']
    for i, dev in enumerate(std_fds):
        fd_path = os.path.join('/proc/self/fd', str(i))
        dev_symlink = os.path.join(dev_path, dev)
        try:
            if not os.path.exists(dev_symlink):
                os.symlink(fd_path, dev_symlink)
        except OSError as e:
            raise OSError(f"Failed to create symlink for {dev}: {e}")

    # Create additional devices
    DEVICES = {
        'null': (stat.S_IFCHR, 1, 3), 'zero': (stat.S_IFCHR, 1, 5),
        'random': (stat.S_IFCHR, 1, 8), 'urandom': (stat.S_IFCHR, 1, 9),
        'console': (stat.S_IFCHR, 136, 1), 'tty': (stat.S_IFCHR, 5, 0),
        'full': (stat.S_IFCHR, 1, 7)
    }

    for device, (dev_type, major, minor) in DEVICES.items():
        device_path = os.path.join(dev_path, device)
        try:
            if not os.path.exists(device_path):
                os.mknod(device_path, 0o666 | dev_type, os.makedev(major, minor))
        except OSError as e:
            raise OSError(f"Failed to create device {device}: {e}")


def _create_mounts(new_root):
    """
    Create and mount necessary filesystems within the container's root.

    Args:
    - new_root (str): Path to the container's new root filesystem.

    Raises:
    - OSError: If directory creation or mount operation fails.
    """
    dirs_to_create = ['proc', 'sys', 'dev', 'dev/pts']

    for dir_name in dirs_to_create:
        full_path = os.path.join(new_root, dir_name)
        try:
            if not os.path.exists(full_path):
                os.makedirs(full_path)
        except OSError as e:
            raise OSError(f"Failed to create directory {dir_name}: {e}")

    try:
        linux.mount('proc', os.path.join(new_root, 'proc'), 'proc', 0, '')
        linux.mount('sysfs', os.path.join(new_root, 'sys'), 'sysfs', 0, '')
        linux.mount('tmpfs', os.path.join(new_root, 'dev'), 'tmpfs', linux.MS_NOSUID | linux.MS_STRICTATIME, 'mode=755')
        makedev(os.path.join(new_root, 'dev'))

        devpts_path = os.path.join(new_root, 'dev', 'pts')
        if not os.path.exists(devpts_path):
            os.makedirs(devpts_path)
        linux.mount('devpts', devpts_path, 'devpts', 0, '')
    except OSError as e:
        raise OSError(f"Failed to mount filesystems: {e}")


def _setup_cpu_cgroup(container_id, container_dir, cpu_shares):
    """
    Setup a CPU cgroup for the container.

    Args:
    - container_id (str): Unique identifier for the container.
    - container_dir (str): Directory to store container-related files.
    - cpu_shares (int): CPU shares (relative weight) for the container.

    Returns:
    - str: Path to the container's CPU cgroup directory.

    Raises:
    - OSError: If cgroup directory creation or file operation fails.
    """
    CPU_CGROUP_BASEDIR = '/sys/fs/cgroup'
    container_cpu_cgroup_dir = os.path.join(CPU_CGROUP_BASEDIR, 'bantubox', container_id)

    try:
        if not os.path.exists(container_cpu_cgroup_dir):
            os.makedirs(container_cpu_cgroup_dir, mode=0o755)

        cgroup_procs_file = os.path.join(container_cpu_cgroup_dir, 'cgroup.procs')
        with open(cgroup_procs_file, 'w') as procs_file:
            procs_file.write(str(os.getpid()))

        pid_file_path = os.path.join(container_dir, container_id, 'pid.txt')
        with open(pid_file_path, 'w') as pid_file:
            pid_file.write(str(os.getpid()))

        if cpu_shares:
            cpu_weight_file = os.path.join(container_cpu_cgroup_dir, 'cpu.weight')
            weight = int(cpu_shares * 100)  # CPU share to weight conversion
            with open(cpu_weight_file, 'w') as weight_file:
                weight_file.write(str(weight))
    except OSError as e:
        raise OSError(f"Failed to setup CPU cgroup: {e}")

    return container_cpu_cgroup_dir


def contain(command, image_name, image_dir, container_id, container_dir, cpu_shares):
    """
    Setup and execute the container environment.

    Args:
    - command (list): Command to be executed in the container.
    - image_name (str): Name of the container image.
    - image_dir (str): Directory where container images are stored.
    - container_id (str): Unique identifier for the container.
    - container_dir (str): Directory for storing container data.
    - cpu_shares (int): CPU shares for the container's cgroup.

    Raises:
    - OSError: If an error occurs in setting up the container environment.
    """
    try:
        _setup_container_environment(container_id)
        new_root = create_container_root(image_name, image_dir, container_id, container_dir)
        print(f'Created a new root fs for our container: {new_root}')
        container_cpu_cgroup_dir = _setup_cpu_cgroup(container_id, container_dir, cpu_shares)
        _create_mounts(new_root)
        _change_root(new_root)
        _execute_command(command, container_cpu_cgroup_dir)
    except OSError as e:
        print(f"Error in container setup: {e}")
        raise

def _setup_container_environment(container_id):
    """
    Set hostname and mount flags for the container.

    Args:
    - container_id (str): Unique identifier for the container.

    Raises:
    - OSError: If an error occurs in setting hostname or mount flags.
    """
    linux.sethostname(container_id)
    linux.mount(None, '/', None, linux.MS_PRIVATE | linux.MS_REC, None)

def _change_root(new_root):
    """
    Change the root filesystem for the container process.

    Args:
    - new_root (str): Path to the new root filesystem.

    Raises:
    - OSError: If changing the root filesystem fails.
    """
    old_root = os.path.join(new_root, 'old_root')
    os.makedirs(old_root, exist_ok=True)
    linux.pivot_root(new_root, old_root)
    os.chdir('/')
    linux.umount2('/old_root', linux.MNT_DETACH)
    os.rmdir('/old_root')

def _execute_command(command, container_cpu_cgroup_dir):
    """
    Execute the given command in the container and read the CPU shares.

    Args:
    - command (list): Command to be executed.
    - container_cpu_cgroup_dir (str): Path to the container's CPU cgroup directory.

    Raises:
    - FileNotFoundError: If the CPU shares file does not exist.
    - OSError: If an error occurs in executing the command.
    """
    try:
        cpu_shares_file = os.path.join(container_cpu_cgroup_dir, 'cpu.shares')
        with open(cpu_shares_file, 'r') as shares_file:
            container_cpu_shares = int(shares_file.read())
            # Use container_cpu_shares as needed
    except FileNotFoundError:
        print("CPU shares file not found.")
        raise

    os.execvp(command[0], command)


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.option('--memory', help='Memory limit in bytes. Use suffixes for larger units (k, m, g)', default=None)
@click.option('--memory-swap', help='Swap limit. -1 for unlimited swap.', default=None)
@click.option('--cpu-shares', help='CPU shares (relative weight)', default=0)
@click.option('--image-name', '-i', help='image name', default='ubuntu')
@click.option('--image-dir', help='Image directory', default=IMAGE_DIR)
@click.option('--container-dir', help='Container directory', default=CONTAINER_DIR)
@click.argument('command', required=True, nargs=-1)
def run(memory, memory_swap, cpu_shares, image_name, image_dir, container_dir, command):
    """
    Run a command in a new container.

    Args:
    - memory, memory_swap, cpu_shares: Resource limits for the container.
    - image_name (str): Name of the container image.
    - image_dir (str): Directory where container images are stored.
    - container_dir (str): Directory for storing container data.
    - command (list): Command to be executed in the container.
    """
    container_id = str(uuid.uuid4())
    flags = linux.CLONE_NEWPID | linux.CLONE_NEWNS | linux.CLONE_NEWUTS | linux.CLONE_NEWNET
    callback_args = (command, image_name, image_dir, container_id, container_dir, cpu_shares, memory, memory_swap)

    try:
        pid = linux.clone(contain, flags, callback_args)
        os.waitpid(pid, 0)
    except Exception as e:
        print(f"Error running container: {e}")


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument('container_id', required=True, nargs=-1)
def stop(container_id):
    """
    Stop a running container.

    Args:
    - container_id (str): Unique identifier of the container to be stopped.
    """
    container_dir = '/home/aropet/bantubox/containers'
    
    for cid in container_id:
        try:
            _stop_single_container(cid, container_dir)
        except Exception as e:
            print(f"Error stopping container {cid}: {e}")

def _stop_single_container(cid, container_dir):
    """
    Stop a single container identified by its ID.

    Args:
    - cid (str): Container ID.
    - container_dir (str): Directory containing container data.

    Raises:
    - FileNotFoundError: If the container's PID file does not exist.
    - ProcessLookupError: If the container process does not exist.
    - OSError: If other OS-level errors occur.
    """
    pid_file_path = os.path.join(container_dir, cid, 'pid.txt')

    if not os.path.exists(pid_file_path):
        raise FileNotFoundError(f"PID file for container {cid} not found.")

    with open(pid_file_path, 'r') as pid_file:
        container_pid = int(pid_file.read())

    os.kill(container_pid, signal.SIGTERM)
    shutil.rmtree(os.path.join(container_dir, cid))
    print(f"Container {cid} stopped and resources cleaned up.")


@cli.command(name='list')
def list_containers():
    """
    List all available containers.
    """
    container_dir = '/home/aropet/bantubox/containers'
    
    try:
        containers = [container for container in os.listdir(container_dir) if os.path.isdir(os.path.join(container_dir, container))]
    except Exception as e:
        print(f"Error listing containers: {e}")
        return

    if not containers:
        print("No containers available.")
    else:
        print("Available containers:")
        for container in containers:
            print(f"- {container}")


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument('container_id', required=True, nargs=-1)
def delete(container_id):
    """
    Delete a specified container.

    Args:
    - container_id (str): Unique identifier of the container to be deleted.
    """
    container_dir = '/home/aropet/bantubox/containers'

    for cid in container_id:
        try:
            _delete_single_container(cid, container_dir)
            print(f"Container {cid} deleted.")
        except Exception as e:
            print(f"Error deleting container {cid}: {e}")

def _delete_single_container(cid, container_dir):
    """
    Delete a single container identified by its ID.

    Args:
    - cid (str): Container ID.
    - container_dir (str): Directory containing container data.

    Raises:
    - FileNotFoundError: If the container directory does not exist.
    - OSError: If errors occur during file operations.
    """
    container_path = os.path.join(container_dir, cid)

    if not os.path.exists(container_path):
        raise FileNotFoundError(f"Container {cid} not found.")

    shutil.rmtree(container_path)


if __name__ == "__main__":
    cli()
