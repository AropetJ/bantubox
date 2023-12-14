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
        image_name (str): The name of the image.
        image_dir (str): The directory where images are stored.
        image_suffix (str, optional): The file extension for the image, default 'tar'.

    Returns:
        str: The path to the image file.

    Raises:
        FileNotFoundError: If the specified image directory does not exist.
    """
    
    # Check if the directory where images are stored exists
    if not os.path.exists(image_dir):
        # If the directory does not exist, raise a FileNotFoundError
        raise FileNotFoundError(f"Image directory '{image_dir}' does not exist.")

    # Construct and return the full file path of the image
    # os.path.join is used to ensure the path is correctly formatted for the operating system
    return os.path.join(image_dir, f"{image_name}.{image_suffix}")


def _get_container_path(container_id, container_dir, *subdir_names):
    """
    Construct a directory path for a created container.

    Args:
        container_id (str): Unique identifier for the container.
        container_dir (str): Base directory for storing container data.
        subdir_names (tuple): Variable number of subdirectory names within the container's directory.

    Returns:
        str: The path to the container's directory.
    
    Raises:
        FileNotFoundError: If the container base directory does not exist.
    """
    
    # Verify if the base directory for storing container data exists
    if not os.path.exists(container_dir):
        # Raise an exception if the base directory is not found
        raise FileNotFoundError(f"Container base directory '{container_dir}' does not exist.")

    # Construct and return the full path to the container's directory
    # Using os.path.join ensures correct path formatting and concatenation
    # The use of *subdir_names allows for a flexible number of subdirectories
    return os.path.join(container_dir, container_id, *subdir_names)


def create_container_root(image_name, image_dir, container_id, container_dir):
    """
    Create a root directory for a container and set up its filesystem.

    Args:
        image_name (str): Name of the container image.
        image_dir (str): Directory where container images are stored.
        container_id (str): Unique identifier for the container.
        container_dir (str): Directory for storing container-related files.

    Returns:
        str: Path to the container's root filesystem.

    Raises:
        FileNotFoundError: If the image file does not exist.
        OSError: If directory creation or file extraction fails.
    """
    # Retrieve the full path to the specified container image
    image_path = _get_image_path(image_name, image_dir)
    # Create a path for the root filesystem of the image
    image_root = os.path.join(image_dir, image_name, 'rootfs')

    # Check if the image file exists at the specified path
    if not os.path.exists(image_path):
        # Raise an error if the image file is not found
        raise FileNotFoundError(f"Unable to locate image {image_name}")

    # If the image root directory doesn't exist, create it and extract the image
    if not os.path.exists(image_root):
        os.makedirs(image_root)  # Create the root filesystem directory
        # Open the tarball image file
        with tarfile.open(image_path) as tar:
            # Filter out character and block device files from the tarball
            members = [m for m in tar.getmembers() if m.type not in (tarfile.CHRTYPE, tarfile.BLKTYPE)]
            # Extract the filtered files into the root filesystem directory
            tar.extractall(image_root, members=members)

    # Create directories for the overlay filesystem components
    container_cow_rw = _get_container_path(container_id, container_dir, 'cow_rw')  # Copy-on-write directory
    container_cow_workdir = _get_container_path(container_id, container_dir, 'cow_workdir')  # Overlay work directory
    container_rootfs = _get_container_path(container_id, container_dir, 'rootfs')  # Mount point for the overlay

    # Ensure these directories exist, creating them if necessary
    for directory in [container_cow_rw, container_cow_workdir, container_rootfs]:
        os.makedirs(directory, exist_ok=True)

    # Prepare the mount options for the overlay filesystem
    mount_options = f"lowerdir={image_root},upperdir={container_cow_rw},workdir={container_cow_workdir}"
    # Mount the overlay filesystem at the container's root filesystem path
    linux.mount('overlay', container_rootfs, 'overlay', linux.MS_NODEV, mount_options)

    # Return the path to the mounted root filesystem of the container
    return container_rootfs


@click.group()
def cli():
    """
    Command-line interface for managing containers with BantuBox.

    This CLI provides commands for running, stopping, listing, and deleting containers.
    
    The `@click.group()` decorator transforms this function into a Click group, 
    which acts as the entry point for a set of subcommands. This is akin to creating 
    a command with multiple actions, like `git push`, `git pull`, etc., where `git` 
    would be the group and `push`, `pull` are its subcommands.
    """
    # The 'pass' statement is used here because this function is not meant to 
    # execute any code itself. Instead, it serves as a holder for the group of 
    # commands that will be attached to it. These commands are defined as separate 
    # functions and are linked to this group through decorators.
    pass


def makedev(dev_path):
    """
    Create device identifiers and special files in the container's /dev directory.

    Args:
    - dev_path (str): The path to the container's /dev directory.

    Raises:
    - OSError: If symlink or device creation fails.
    """

    # Standard file descriptors (stdin, stdout, stderr) are created as symlinks
    # to corresponding file descriptors of the host process.
    std_fds = ['stdin', 'stdout', 'stderr']
    for i, dev in enumerate(std_fds):
        fd_path = os.path.join('/proc/self/fd', str(i))  # Path to the host's file descriptor
        dev_symlink = os.path.join(dev_path, dev)  # Path for the symlink in the container's /dev directory
        try:
            if not os.path.exists(dev_symlink):  # Check if symlink already exists
                os.symlink(fd_path, dev_symlink)  # Create a symlink to the host's file descriptor
        except OSError as e:
            raise OSError(f"Failed to create symlink for {dev}: {e}")  # Raise error if symlink creation fails

    # Creating additional device nodes.
    # These devices include /dev/null, /dev/zero, etc., which are commonly required in a Linux environment.
    DEVICES = {
        'null': (stat.S_IFCHR, 1, 3),  # Character device, Major number 1, Minor number 3
        'zero': (stat.S_IFCHR, 1, 5),
        'random': (stat.S_IFCHR, 1, 8),
        'urandom': (stat.S_IFCHR, 1, 9),
        'console': (stat.S_IFCHR, 136, 1),
        'tty': (stat.S_IFCHR, 5, 0),
        'full': (stat.S_IFCHR, 1, 7)
    }

    for device, (dev_type, major, minor) in DEVICES.items():
        device_path = os.path.join(dev_path, device)  # Path for the device node in the container's /dev directory
        try:
            if not os.path.exists(device_path):  # Check if device node already exists
                os.mknod(device_path, 0o666 | dev_type, os.makedev(major, minor))  # Create the device node
        except OSError as e:
            raise OSError(f"Failed to create device {device}: {e}")  # Raise error if device node creation fails


def _create_mounts(new_root):
    """
    Create essential filesystem mounts in the container's new root.

    Args:
    - new_root (str): Path to the container's new root filesystem.
    
    Raises:
    - OSError: If an error occurs during the mount operations.
    """
    try:
        # Mount the 'proc' filesystem at /proc.
        # This is essential for processes within the container to access process information.
        proc_path = os.path.join(new_root, 'proc')
        linux.mount('proc', proc_path, 'proc', 0, '')

        # Mount the 'sysfs' filesystem at /sys.
        # This provides information about kernel and connected devices.
        sysfs_path = os.path.join(new_root, 'sys')
        linux.mount('sysfs', sysfs_path, 'sysfs', 0, '')

        # Mount a 'tmpfs' filesystem at /dev.
        # This is a temporary file storage used for creating device files.
        dev_path = os.path.join(new_root, 'dev')
        linux.mount('tmpfs', dev_path, 'tmpfs', linux.MS_NOSUID | linux.MS_STRICTATIME, 'mode=755')

        # Mount the 'devpts' filesystem to enable pseudo-terminal devices (PTYs).
        # Necessary for terminal emulation within the container.
        devpts_path = os.path.join(dev_path, 'pts')
        if not os.path.exists(devpts_path):
            os.makedirs(devpts_path)  # Create the directory if it doesn't exist.
        linux.mount('devpts', devpts_path, 'devpts', 0, '')

        # Call makedev function to create essential device nodes in /dev.
        makedev(dev_path)

    except OSError as e:
        raise OSError(f"Failed to create mounts: {e}")  # Handle exceptions during mount operations.



def _setup_cpu_cgroup(container_id, cpu_shares):
    """
    Setup a CPU cgroup for the container.

    Args:
    - container_id (str): Unique identifier for the container.
    - cpu_shares (int): CPU shares (relative weight) for the container.

    Raises:
    - OSError: If cgroup directory creation or file operation fails.
    """
    # Define the base directory for CPU cgroups
    CPU_CGROUP_BASEDIR = '/sys/fs/cgroup/cpu'
    
    # Construct the path for the container's specific CPU cgroup directory
    container_cpu_cgroup_dir = os.path.join(CPU_CGROUP_BASEDIR, 'bantubox', container_id)

    # Check if the container's CPU cgroup directory exists, create it if not
    if not os.path.exists(container_cpu_cgroup_dir):
        os.makedirs(container_cpu_cgroup_dir)

    # Path for the 'tasks' file within the CPU cgroup directory
    tasks_file = os.path.join(container_cpu_cgroup_dir, 'tasks')
    try:
        # Open the 'tasks' file and write the current process ID (PID)
        with open(tasks_file, 'w') as file:
            file.write(str(os.getpid()))
    except OSError as e:
        # Handle any exceptions related to file operations
        raise OSError(f"Failed to write to tasks file: {e}")

    # Check if cpu_shares is specified (non-zero) and set CPU shares for the container
    if cpu_shares:
        # Path for the 'cpu.shares' file within the CPU cgroup directory
        cpu_shares_file = os.path.join(container_cpu_cgroup_dir, 'cpu.shares')
        try:
            # Open the 'cpu.shares' file and write the specified CPU shares
            with open(cpu_shares_file, 'w') as file:
                file.write(str(cpu_shares))
        except OSError as e:
            # Handle any exceptions related to file operations
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
        # Set up the CPU cgroup for resource allocation
        _setup_cpu_cgroup(container_id, cpu_shares)

        # Set the hostname of the container to its unique ID
        linux.sethostname(container_id)

        # Make all mounts in the current namespace private
        linux.mount(None, '/', None, linux.MS_PRIVATE | linux.MS_REC, None)

        # Create a new filesystem root for the container
        new_root = create_container_root(image_name, image_dir, container_id, container_dir)

        # Set up necessary filesystem mounts within the new root
        _create_mounts(new_root)

        # Change the working directory to the new root
        os.chdir(new_root)

        # Prepare for changing the root filesystem
        old_root = os.path.join(new_root, 'old_root')
        if not os.path.exists(old_root):
            # Create a directory for the old root if it doesn't exist
            os.makedirs(old_root)

        # Perform the pivot_root operation
        linux.pivot_root(new_root, old_root)

        # Change the current working directory to the new root
        os.chdir('/')

        # Unmount and attempt to remove the old root directory
        linux.umount2('/old_root', linux.MNT_DETACH)
        if os.path.exists(old_root) and not os.listdir(old_root):
            # Remove the old root directory if it's empty
            os.rmdir(old_root)

        # Execute the specified command within the container environment
        os.execvp(command[0], command)

    except OSError as e:
        # Handle any exceptions that occur during container setup
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
