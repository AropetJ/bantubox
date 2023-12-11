#!/home/aropet/bantubox/bb3venv/bin/python3

"""
BantuBox - A simple docker like application for running linux containers
Usage:
    running:
        sudo ./bb.py run <commad> <options>
"""

import os #file and process management
import uuid #unique container ids
import tarfile #extracting the image tarball file
import stat
import click #command line utility
import linux #linux sys call wrappers

class ContainerUtils:
    @staticmethod
    def _get_image_path(image_name, image_dir, image_suffix='tar'):
        """Returns a path to a directory containing the base image

        Args:
            image_name (str): The name of the image eg ubuntu
            image_dir (str): The directory in which the image is located
            image_suffix (str, optional): The extension of the image file. Defaults to 'tar'.
        """
        return os.path.join(image_dir, image_name + os.extsep + image_suffix) #creates a path image_dir/image_name.tar
    

    @staticmethod
    def _get_container_path(container_id, container_dir, *subdir_names):
        """Returns a path to a container location

        Args:
            container_id (str): The container ID
            container_dir (str): The directory in which the container will be located
        """
        return os.path.join(container_dir, container_id, *subdir_names) #Creates a path to container dir container_dir/container_id/subdirs
    

    @staticmethod
    def makedev(dev_path):
        """Creates device identifiers with mknod

        Args:
            dev_path (str): A path to the device nodes
        """
        for i, dev in enumerate(['stdin', 'stdout', 'stderr']): #iterate through the list, assign each value an index
            os.symlink(f'/proc/self/fd/{i}', os.path.join(dev_path, dev)) #creates a symbolic link pointing from /proc/self/fd/i (which is typically the stdin, stdout and stderr) to the file inside the dev directory of the container's new root.
        os.symlink('/proc/self/fd', os.path.join(dev_path, 'fd'))
        #Adding some extra devices
        DEVICES = {'null': (stat.S_IFCHR, 1, 3), 'zero': (stat.S_IFCHR, 1, 5),
                   'random': (stat.S_IFCHR, 1, 8), 'urandom': (stat.S_IFCHR, 1,9),
                   'console': (stat.S_IFCHR, 136, 1), 'tty': (stat.S_IFCHR, 5, 0),
                   'full': (stat.S_IFCHR, 1, 7)}
        for device, (dev_type, major, minor) in DEVICES.items():
            os.mknod(os.path.join(dev_path, device), 0o666 | dev_type, os.makedev(major, minor))
