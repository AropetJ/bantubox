#!/home/aropet/bantubox/bb3venv/bin/python3

"""
BantuBox - A simple docker like application for running linux containers
Usage:
    running:
        sudo ./bb.py run <commad> <options>
"""

import os
import uuid
import tarfile
import stat
import click
from containerutils import ContainerUtils
import linux

class ContainerManager:
    """
    Base class for creating and managing containers
    """
    def __init__(self, image_name, image_dir, container_dir):
        self.image_name = image_name
        self.image_dir = image_dir
        self.container_dir = container_dir
        self.container_id = str(uuid.uuid4())
    

    def create_container_root(self):
        """
        This function is used to set up the root filesystem for a container. It
        takes the name of the image to use, the directory containing the image, the
        ID of the container, and the directory to store the container data.
        
        If the image rootfs does not already exist, this function extracts the image
        tarball to create it. It then creates the necessary directories for the 
        container's overlay mount and performs the overlay mount.

        Args:
            image_name (str): The name of the image to use.
            image_dir (str): The directory containing the image.
            container_id (str): The ID of the container.
            container_dir (str): The directory to store the container data.

        Returns:
            str: The path to the container's root filesystem.
        """
        image_path = ContainerUtils._get_image_path(self.image_name, self.image_dir)
    
        image_root = os.path.join(self.image_dir, self.image_name, 'rootfs')

        assert os.path.exists(image_path), f"Unable to locate image {self.image_name}"

        if not os.path.exists(image_root):
            os.makedirs(image_root)
            with tarfile.open(image_path) as tar_file:
                all_members = tar_file.getmembers()

                filtereed_members = []
                for member in all_members:
                    if member.type not in (tarfile.CHRTYPE, tarfile.BLKTYPE):
                        filtereed_members.append(member)
                tar_file.extractall(image_root, members=filtereed_members)

        container_cow_rw = ContainerUtils._get_container_path(
            self.container_id, self.container_dir, 'cow_rw')
        container_cow_workdir = ContainerUtils._get_container_path(
            self.container_id, self.container_dir, 'cow_workdir')
        container_rootfs = ContainerUtils._get_container_path(
            self.container_id, self.container_dir, 'rootfs')
    
        for d in (container_cow_rw, container_cow_workdir, container_rootfs):
            if not os.path.exists(d):
                os.makedirs(d)

        linux.mount(
            'overlay', container_rootfs, 'overlay', linux.MS_NODEV,
            "lowerdir={image_root},upperdir={cow_rw},workdir={cow_workdir}".format(
                image_root=image_root,
                cow_rw=container_cow_rw,
                cow_workdir=container_cow_workdir))
    
        return container_rootfs
    

    def makedev(self, dev_path):
        """
        This function creates device identifiers in the given directory by creating
        symbolic links from the current process's file descriptors. It also adds
        some extra devices, such as 'null', 'zero', 'random', 'urandom', 'console',
        'tty', and 'full'.

        Args:
            dev_path (str): The path to the directory where the device identifiers
            will be created.

        Returns:
            None
        """
        for i, dev in enumerate(['stdin', 'stdout', 'stderr']):
            os.symlink('/proc/self/fd', os.path.join(dev_path, 'fd'))

        DEVICES = {'null': (stat.S_IFCHR, 1, 3), 'zero': (stat.S_IFCHR, 1, 5),
                   'random': (stat.S_IFCHR, 1, 8), 'urandom': (stat.S_IFCHR, 1,9),
                   'console': (stat.S_IFCHR, 136, 1), 'tty': (stat.S_IFCHR, 5, 0),
                   'full': (stat.S_IFCHR, 1, 7)}
        for device, (dev_type, major, minor) in DEVICES.items():
            os.mknod(os.path.join(dev_path, device), 0o666 | dev_type, os.makedev(major, minor))
    

    def _create_mounts(self, new_root):
        """
        Create mount points for sys, dev, proc and basic devices(stdin, stdout,
        stderr) in a new root directory.

        Args:
            new_root (_type_): The path to the new root directory where the
            mount points will be created.

        Returns: None
        """
        linux.mount('proc', os.path.join(new_root, 'proc'), 'proc', 0, '')
        linux.mount('sysfs', os.path.join(new_root, 'sys'), 'sysfs', 0, '')
        linux.mount('tmpfs', os.path.join(new_root, 'dev'), 'tmpfs', 
                linux.MS_NOSUID | linux.MS_STRICTATIME, 'mode=755')
    
        devpts_path = os.path.join(new_root, 'dev', 'pts')
        if not os.path.exists(devpts_path):
            os.makedirs(devpts_path)
            linux.mount('devpts', devpts_path, 'devpts', 0, '')

        self.makedev(os.path.join(new_root, 'dev'))


    def contain(self, command, cpu_shares):
        """
        Contain function that sets up the necessary environment for the container
        process.
    
        This function includes steps like changing the hostname, chrooting/jailing
        the process, mounting the filesystem, creating a namespace, and setting up
        a cgroup for CPU shares.

        Args:
            command (List[str]): The command to be executed in the container
            cpu_shares (int): The number of CPU shares for the container process
        """
        linux.sethostname(self.container_id)

        linux.mount(None, '/', None, linux.MS_PRIVATE | linux.MS_REC, None)

        new_root = self.create_container_root(
            self.image_name, self.image_dir, self.container_id, self.container_dir)

        self._create_mounts(new_root)

        old_root = os.path.join(new_root, 'old_root')
        os.makedirs(old_root)
        linux.pivot_root(new_root, old_root)

        os.chdir('/')

        linux.umount2('/old_root', linux.MNT_DETACH)
        os.rmdir('/old_root')

        os.execvp(command[0], command)
