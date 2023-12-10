#!/usr/bin/python3

"""
BantuBox - A simple docker like application for running linux containers
Usage:
    running:
        python3 bb.py run <commad> <options>
"""

import click #command line utility
import os #file and process management
import traceback #traceback errors
import uuid #unique container ids
import tarfile #extracting the image tarball file

#Creates a directory path for the image, we shall use this to create a container
def _get_image_path(image_name, image_dir, image_suffix='tar'):
    return os.path.join(image_dir, os.path.extsep([image_name, image_suffix]))


#Create a directory path for a created container, i.e a container is created in a path
#specified here
def _get_container_path(container_id, container_dir, *subdir_names):
    return os.path.join(container_dir, container_id, *subdir_names)


#Creates a root directory for our container which we shall then chroot
def create_container_root(image_name, image_dir, container_id, container_dir):
    image_path = _get_image_path(image_name, image_dir)
    container_root = _get_container_path(container_id, container_dir, 'rootfs')
    assert os.path.exists(image_path), f"unable to locate image {image_name}"
    os.makedirs(container_root, exist_ok=True) #Create a directory if it does not exist

    #Extract the contents of the tarball file into the rootfs
    with tarfile.open(image_path) as tar_file:
        all_members = tar_file.getmembers()

        filtereed_members = []
        for member in all_members:
            if member.type not in (tarfile.CHRTYPE, tarfile.BLKTYPE):
                filtereed_members.append(member)
        tar_file.extractall(container_root, members=filtereed_members)

    return container_root


#Click group to custmise our command in the cmdline, we'll add more arguments here
@click.group()
def cli():
    pass


#The exec function will be called here to overwrite the forked process and runa new
#process. We then chroot/jail the process, mount it the file system, add a namespace
#and create a cgroup for it
def contain(command, image_name, image_dir, container_id, container_dir):
    os.execvp(command[0], command)


#The run function is the main function that will be called when the user runs. It's
#our main commandline utility
@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.option('--image-name', '-i', help='image name', default='ubuntu')
@click.option('--image-dir', help='Image directory', default= '/home/aropet/studies/bantuboxv3/images')
@click.option('--container-dir', help='Container directory', default= '/home/aropet/studies/bantuboxv3/containers')
@click.argument('command', required=True, nargs=-1)
def run(image_name, image_dir, container_dir, command):
    #Create a unique container id when we run
    container_id = str(uuid.uuid4())

    #Fork the current process in command
    pid = os.fork()

    #Check if fork succeeded or failed
    if pid == 0:
        try:
            #Run the exec command to replace the forked process with a new one
            contain(command, image_name, image_dir, container_id, container_dir)
        except Exception as e:
            #Return omething happened and exec failed
            traceback.print_exc()
            os._exit(1)
    #Wait block for the parent process
    wait_pid, status = os.waitpid(pid, 0)
    print(f"{wait_pid} exited with status {status}")


#The command line utility for stopping a running container
@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument('container_id', required=True, nargs=-1)
def stop(container_id):
    print(f"Stopping container: {container_id}")


#The command line utility for listing all available containers
@cli.command(name='list')
def list_containers():
    print("These are the available containers: ")


if __name__ == "__main__":
    cli()
