#!/usr/bin/python3

"""
BantuBox - A simple docker like application for running linux containers
Usage:
    running:
        python3 bb.py run <commad> <options>
"""

import click
import os
import traceback


#Click group to custmise our command in the cmdline, we'll add more arguments here
@click.group()
def cli():
    pass


#The exec function will be called here to overwrite the forked process and runa new
#process. We then chroot/jail the process, mount it the file system, add a namespace
#and create a cgroup for it
def contain(command):
    os.execvp(command[0], command)


#The run function is the main function that will be called when the user runs. It's
#our main commandline utility
@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument('command', required=True, nargs=-1)
def run(command):
    #Fork the command
    pid = os.fork()

    #Check if fork succeeded or failed
    if pid == 0:
        try:
            #Run the exec command if fork succeeded
            contain(command)
        except Exception as e:
            #Return omething happened and exec failed
            traceback.print_exc()
            os._exit(1)
    #Wait block for the parent process
    _, status = os.waitpid(pid, 0)
    print(f"{pid} exited with status {status}")


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
