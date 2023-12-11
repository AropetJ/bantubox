#!/home/aropet/studies/bantuboxv3/bb3venv/bin/python3

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
import linux #linux sys call wrappers
import stat

#Creates a directory path for the image, we shall use this to create a container
def _get_image_path(image_name, image_dir, image_suffix='tar'): # Declares the function
    return os.path.join(image_dir, image_name + os.extsep + image_suffix) #creates a path image_dir/image_name.tar


#Create a directory path for a created container, i.e a container is created in a path
#specified here
def _get_container_path(container_id, container_dir, *subdir_names): #Declares the function
    return os.path.join(container_dir, container_id, *subdir_names) #Creates a path to container dir container_dir/container_id/subdirs


#Creates a root directory for our container which we shall then chroot
def create_container_root(image_name, image_dir, container_id, container_dir): #Create a directory for the container rootfs
    image_path = _get_image_path(image_name, image_dir) #Get the image path
    # print(image_path)
    image_root = os.path.join(image_dir, image_name, 'rootfs')

    assert os.path.exists(image_path), f"Unable to locate image {image_name}"

    #Create a directory if it does not exist
    if not os.path.exists(image_root): #Create the path if it doesnot exist
        os.makedirs(image_root)
        #Extract the contents of the tarball file into the rootfs
        with tarfile.open(image_path) as tar_file:
            all_members = tar_file.getmembers() #Get all members

            filtereed_members = [] #Initialize a list of filtered members
            for member in all_members: #Iterate through the list
                if member.type not in (tarfile.CHRTYPE, tarfile.BLKTYPE): #Exclude the two types of files
                    filtereed_members.append(member) #append to list
            tar_file.extractall(image_root, members=filtereed_members) #Extract all to the file path we created

    # Create directories for copy-on-write (uppperdir), overlay workdir,
    # and a mount point
    container_cow_rw = _get_container_path(
        container_id, container_dir, 'cow_rw')
    container_cow_workdir = _get_container_path(
        container_id, container_dir, 'cow_workdir')
    container_rootfs = _get_container_path(
        container_id, container_dir, 'rootfs')
    
    for d in (container_cow_rw, container_cow_workdir, container_rootfs):
        if not os.path.exists(d):
            os.makedirs(d)

    # Mount the overlay (HINT: use the MS_NODEV flag to mount)
    linux.mount(
        'overlay', container_rootfs, 'overlay', linux.MS_NODEV,
        "lowerdir={image_root},upperdir={cow_rw},workdir={cow_workdir}".format(
            image_root=image_root,
            cow_rw=container_cow_rw,
            cow_workdir=container_cow_workdir))
    
    return container_rootfs #Return a path to the rootfs


#Click group to custmise our command in the cmdline, we'll add more arguments here
@click.group()
def cli():
    pass


#Creating device identifiers with mknod
def makedev(dev_path):
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


#Creating new mounts
def _create_mounts(new_root):
    #Create mount points in sys, dev, proc in our new_root
    linux.mount('proc', os.path.join(new_root, 'proc'), 'proc', 0, '') #Mount the proc file system on our proc dir
    linux.mount('sysfs', os.path.join(new_root, 'sys'), 'sysfs', 0, '') #Mount the sysfs file system on our sys dir
    linux.mount('tmpfs', os.path.join(new_root, 'dev'), 'tmpfs', 
                linux.MS_NOSUID | linux.MS_STRICTATIME, 'mode=755') #Mount the tmpfs file system on our dev dir
    
    #Adding some basic devices to our file system(stdin, stdout, stderr)
    devpts_path = os.path.join(new_root, 'dev', 'pts') #Create a path to mount our basic devices
    if not os.path.exists(devpts_path): #Check if the path exists
        os.makedirs(devpts_path) #Make the path if it does not exist
        linux.mount('devpts', devpts_path, 'devpts', 0, '') #Mount devpts files system to our dev path

    makedev(os.path.join(new_root, 'dev'))


#The exec function will be called here to overwrite the forked process and runa new
#process. We then chroot/jail the process, mount it the file system, add a namespace
#and create a cgroup for it
def contain(command, image_name, image_dir, container_id, container_dir):
    linux.unshare(linux.CLONE_NEWNS) #unshare from the parent process namespace

    linux.mount(None, '/', None, linux.MS_PRIVATE | linux.MS_REC, None)

    new_root = create_container_root(
        image_name, image_dir, container_id, container_dir)
    print('Created a new root fs for our container: {}'.format(new_root))

    _create_mounts(new_root)

    old_root = os.path.join(new_root, 'old_root')
    os.makedirs(old_root)
    linux.pivot_root(new_root, old_root)

    os.chdir('/')

    linux.umount2('/old_root', linux.MNT_DETACH)  # umount old root
    os.rmdir('/old_root')  # rmdir the old_root dir

    os.execvp(command[0], command)


#The run function is the main function that will be called when the user runs. It's
#our main commandline utility
@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.option('--image-name', '-i', help='image name', default='ubuntu')
@click.option('--image-dir', help='Image directory', default='/home/aropet/studies/bantubox/images')
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
    wait_pid, status = os.waitpid(pid, 0) #Get the status of the forked processes
    print(f"{wait_pid} exited with status {status}") #Print the exit status


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
