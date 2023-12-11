#!/home/aropet/bantubox/bb3venv/bin/python3

"""
BantuBox - A simple docker like application for running linux containers
Usage:
    running:
        sudo ./bb.py run <commad> <options>
"""

import os
import uuid
import click
import linux
from containermanager import ContainerManager
from containerutils import ContainerUtils


@click.group()
def cli():
    pass


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.option('--cpu-shares', help='CPU shares (relative weight)', default=0)
@click.option('--image-name', '-i', help='image name', default='ubuntu')
@click.option('--image-dir', help='Image directory', default='/home/aropet/bantubox/images')
@click.option('--container-dir', help='Container directory', default= '/home/aropet/bantubox/containers')
@click.argument('command', required=True, nargs=-1)
def run(cpu_shares, image_name, image_dir, container_dir, command):
    """_summary_

    Args:
        cpu_shares (_type_): _description_
        image_name (_type_): _description_
        image_dir (_type_): _description_
        container_dir (_type_): _description_
        command (_type_): _description_
    """
    manager = ContainerManager(image_name, image_dir, container_dir)
    container_id = manager.container_id

    flags = (linux.CLONE_NEWPID | linux.CLONE_NEWNS | linux.CLONE_NEWUTS | linux.CLONE_NEWNET)
    callback_args = (command, image_name, image_dir, container_id, container_dir, cpu_shares)

    pid = linux.clone(manager.contain, flags, callback_args)

    wait_pid, status = os.waitpid(pid, 0)
    print(f"{wait_pid} exited with status {status}")


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument('container_id', required=True, nargs=-1)
def stop(container_id):
    """
    The command line utility for stopping a running container

    Args:
        container_id (str): The container ID
    """
    print(f"Stopping container: {container_id}")


@cli.command(name='list')
def list_containers():
    """
    The command line utility for listing all available containers
    """
    print("These are the available containers: ")


if __name__ == "__main__":
    cli()
