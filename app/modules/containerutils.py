#!/home/aropet/bantubox/bb3venv/bin/python3

"""
BantuBox - A simple docker like application for running linux containers
Usage:
    running:
        sudo ./bb.py run <commad> <options>
"""

import os
import tarfile
import stat
import linux

class ContainerUtils:
    """
    Base class for handling container utilities like directories and device files
    """
    @staticmethod
    def _get_image_path(image_name, image_dir, image_suffix='tar'):
        """Returns a path to a directory containing the base image

        Args:
            image_name (str): The name of the image eg ubuntu
            image_dir (str): The directory in which the image is located
            image_suffix (str, optional): The extension of the image file. Defaults to 'tar'.
        """
        return os.path.join(image_dir, image_name + os.extsep + image_suffix)
    

    @staticmethod
    def _get_container_path(container_id, container_dir, *subdir_names):
        """Returns a path to a container location

        Args:
            container_id (str): The container ID
            container_dir (str): The directory in which the container will be located
        """
        return os.path.join(container_dir, container_id, *subdir_names)
    

    @staticmethod
    def makedev(dev_path):
        """Creates device identifiers with mknod

        Args:
            dev_path (str): A path to the device nodes
        """
        for i, dev in enumerate(['stdin', 'stdout', 'stderr']):
            os.symlink(f'/proc/self/fd/{i}', os.path.join(dev_path, dev))

        DEVICES = {'null': (stat.S_IFCHR, 1, 3), 'zero': (stat.S_IFCHR, 1, 5),
                   'random': (stat.S_IFCHR, 1, 8), 'urandom': (stat.S_IFCHR, 1,9),
                   'console': (stat.S_IFCHR, 136, 1), 'tty': (stat.S_IFCHR, 5, 0),
                   'full': (stat.S_IFCHR, 1, 7)}
        for device, (dev_type, major, minor) in DEVICES.items():
            os.mknod(os.path.join(dev_path, device), 0o666 | dev_type, os.makedev(major, minor))
