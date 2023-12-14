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
    Create a root directory for a container and set up its filesystem.

    Args:
    - image_name (str): Name of the container image.
    - image_dir (str): Directory where container images are stored.
    - container_id (str): Unique identifier for the container.
    - container_dir (str): Directory for storing container-related files.

    Returns:
    - str: Path to the container's root filesystem.

    Raises:
    - FileNotFoundError: If the image file does not exist.
    - OSError: If directory creation or file extraction fails.
    """
    image_path = _get_image_path(image_name, image_dir)
    image_root = os.path.join(image_dir, image_name, 'rootfs')

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Unable to locate image {image_name}")

    if not os.path.exists(image_root):
        os.makedirs(image_root)
        with tarfile.open(image_path) as tar:
            members = [m for m in tar.getmembers() if m.type not in (tarfile.CHRTYPE, tarfile.BLKTYPE)]
            tar.extractall(image_root, members=members)

    # Create directories for copy-on-write, overlay workdir, and a mount point
    container_cow_rw = _get_container_path(container_id, container_dir, 'cow_rw')
    container_cow_workdir = _get_container_path(container_id, container_dir, 'cow_workdir')
    container_rootfs = _get_container_path(container_id, container_dir, 'rootfs')

    for directory in [container_cow_rw, container_cow_workdir, container_rootfs]:
        os.makedirs(directory, exist_ok=True)

    # Mount the overlay filesystem
    mount_options = f"lowerdir={image_root},upperdir={container_cow_rw},workdir={container_cow_workdir}"
    linux.mount('overlay', container_rootfs, 'overlay', linux.MS_NODEV, mount_options)

    return container_rootfs


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
    Create essential filesystem mounts in the container's new root.

    Args:
    - new_root (str): Path to the container's new root filesystem.
    
    Raises:
    - OSError: If an error occurs during the mount operations.
    """
    try:
        # Mount the 'proc' filesystem
        proc_path = os.path.join(new_root, 'proc')
        linux.mount('proc', proc_path, 'proc', 0, '')

        # Mount the 'sysfs' filesystem
        sysfs_path = os.path.join(new_root, 'sys')
        linux.mount('sysfs', sysfs_path, 'sysfs', 0, '')

        # Mount the 'tmpfs' filesystem on /dev
        dev_path = os.path.join(new_root, 'dev')
        linux.mount('tmpfs', dev_path, 'tmpfs', linux.MS_NOSUID | linux.MS_STRICTATIME, 'mode=755')

        # Mount the 'devpts' filesystem to enable PTYs
        devpts_path = os.path.join(dev_path, 'pts')
        if not os.path.exists(devpts_path):
            os.makedirs(devpts_path)
        linux.mount('devpts', devpts_path, 'devpts', 0, '')

        # Create basic device nodes in /dev
        makedev(dev_path)

    except OSError as e:
        raise OSError(f"Failed to create mounts: {e}")


def _setup_cpu_cgroup(container_id, cpu_shares):
    """
    Setup a CPU cgroup for the container.

    Args:
    - container_id (str): Unique identifier for the container.
    - cpu_shares (int): CPU shares (relative weight) for the container.

    Raises:
    - OSError: If cgroup directory creation or file operation fails.
    """
    CPU_CGROUP_BASEDIR = '/sys/fs/cgroup/cpu'
    container_cpu_cgroup_dir = os.path.join(CPU_CGROUP_BASEDIR, 'bantubox', container_id)

    # Create the cgroup directory for the container if it doesn't exist
    if not os.path.exists(container_cpu_cgroup_dir):
        os.makedirs(container_cpu_cgroup_dir)

    # Write the container's process ID to the 'tasks' file
    tasks_file = os.path.join(container_cpu_cgroup_dir, 'tasks')
    try:
        with open(tasks_file, 'w') as file:
            file.write(str(os.getpid()))
    except OSError as e:
        raise OSError(f"Failed to write to tasks file: {e}")

    # Set the CPU shares for the container if cpu_shares is specified
    if cpu_shares:
        cpu_shares_file = os.path.join(container_cpu_cgroup_dir, 'cpu.shares')
        try:
            with open(cpu_shares_file, 'w') as file:
                file.write(str(cpu_shares))
        except OSError as e:
            raise OSError(f"Failed to set cpu shares: {e}")


def contain(command, image_name, image_dir, container_id, container_dir, cpu_shares, memory, memory_swap):
    """
    Set up and execute the container environment.

    Args:
    - command (list): Command to be executed in the container.
    - image_name (str): Name of the container image.
    - image_dir (str): Directory where container images are stored.
    - container_id (str): Unique identifier for the container.
    - container_dir (str): Directory for storing container data.
    - cpu_shares (int): CPU shares for the container's cgroup.
    - memory (int): Memory limit in bytes.
    - memory_swap (int): Total limit for the combined used memory and swap.

    Raises:
    - OSError: If an error occurs in setting up the container environment.
    """
    try:
        # Set up CPU cgroup
        _setup_cpu_cgroup(container_id, cpu_shares)

        # Change hostname to container_id
        linux.sethostname(container_id)

        # Make all mounts private
        linux.mount(None, '/', None, linux.MS_PRIVATE | linux.MS_REC, None)

        # Create a new root filesystem for the container
        new_root = create_container_root(image_name, image_dir, container_id, container_dir)
        # print(f'Created a new rootfs for our container: {new_root}')

        # Create necessary mounts within the new root
        _create_mounts(new_root)
        os.chdir(new_root)

        # Change the root of the filesystem to the new root
        old_root = os.path.join(new_root, 'old_root')
        if not os.path.exists(old_root):
            os.makedirs(old_root)
        
        linux.pivot_root(new_root, old_root)

        os.chdir('/')

        # Unmount and remove the old root directory
        linux.umount2('/old_root', linux.MNT_DETACH)
        # print(old_root)

        # Check if old_root is empty before attempting to remove it
        if os.path.exists(old_root) and not os.listdir(old_root):
            os.rmdir(old_root)
        else:
            # print(f"Warning: Unable to remove {old_root}. It may still be in use.")
            print()

        # Execute the command within the container
        os.execvp(command[0], command)

    except OSError as e:
        print(f"Error in container setup: {e}")
        raise


@cli.command(context_settings={'ignore_unknown_options': True})
@click.option('--memory', help='Memory limit in bytes. Use suffixes (k, m, g) for larger units.', default=None)
@click.option('--memory-swap', help='Total memory plus swap limit. Specify -1 for unlimited swap.', default=None)
@click.option('--cpu-shares', help='CPU shares (relative weight)', default=0)
@click.option('--image-name', '-i', help='Image name', default='ubuntu')
@click.option('--image-dir', help='Images directory', default=IMAGE_DIR)
@click.option('--container-dir', help='Containers directory', default=CONTAINER_DIR)
@click.argument('command', required=True, nargs=-1)
def run(memory, memory_swap, cpu_shares, image_name, image_dir, container_dir, command):
    """
    Run a command in a new container.

    Args:
    - memory (str): Memory limit in bytes.
    - memory_swap (str): Total memory plus swap limit.
    - cpu_shares (int): CPU shares for the container.
    - image_name (str): Name of the container image.
    - image_dir (str): Directory where container images are stored.
    - container_dir (str): Directory for storing container data.
    - command (tuple): Command to be executed in the container.
    """
    container_id = str(uuid.uuid4())

    # Flags for namespaces to be created for the new container process
    flags = linux.CLONE_NEWPID | linux.CLONE_NEWNS | linux.CLONE_NEWUTS | linux.CLONE_NEWNET

    # Arguments for the container setup callback function
    callback_args = (command, image_name, image_dir, container_id, container_dir, cpu_shares, memory, memory_swap)

    # Create a new process for the container
    pid = linux.clone(contain, flags, callback_args)

    # Wait for the container process to complete and fetch its exit status
    _, status = os.waitpid(pid, 0)
    print(f'Container process {pid} exited with status {status}')


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
