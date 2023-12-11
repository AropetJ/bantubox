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
    

    def create_container_root(image_name, image_dir, container_id, container_dir):
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
        image_path = ContainerUtils._get_image_path(image_name, image_dir)
    
        image_root = os.path.join(image_dir, image_name, 'rootfs')

        assert os.path.exists(image_path), f"Unable to locate image {image_name}"

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
            container_id, container_dir, 'cow_rw')
        container_cow_workdir = ContainerUtils._get_container_path(
            container_id, container_dir, 'cow_workdir')
        container_rootfs = ContainerUtils._get_container_path(
            container_id, container_dir, 'rootfs')
    
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
