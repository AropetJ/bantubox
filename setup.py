#!/home/aropet/studies/bantuboxv3/bb3venv/bin/python3

from setuptools import setup, Extension

module = Extension('linux',
                   sources=['linux.c'],
                   extra_compile_args=['-D_GNU_SOURCE'])

setup(name='linux',
      version=3.0,
      description='The linux module is a simple Python c extension, containing syscall wrappers missing from the Python os module. You will need to use these system calls to implement different aspect of process containment during the workshop.',
      ext_modules=[module])
