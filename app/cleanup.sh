#!/usr/bin/env bash
#
# The dirtiest cleanup script
#

# don't interfere with umount
pushd /

# umount stuff
while $(grep -q bantubox /proc/mounts); do 
    sudo umount $(grep bantubox /proc/mounts | shuf | head -n1 | cut -f2 -d' ') 2>/dev/null
done

# remove stuff
sudo rm -rf /bantubox/containers/*

popd
