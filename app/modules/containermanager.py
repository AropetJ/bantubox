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

