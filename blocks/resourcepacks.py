""" Handles the loading of resource packs.

    This gets messy. Cause; windows!

    \\ is love, \\ is life
"""

import bpy
import os
import sys

from os import path
from zipfile import ZipFile
from Mineblend.sysutil import MCPATH


settings = path.join(MCPATH, "options.txt")
versions = path.join(MCPATH, "versions")
archive = path.sep.join([versions, "1.9", "1.9.jar"])

assets = path.join("assets", "minecraft")

textures = path.join(assets, "textures")
states = path.join(assets, "blockstates")
models = path.join(assets, "models")

MBDIR = os.path.join(MCPATH, 'mineblend')

if not path.exists(MBDIR):
    os.makedirs(MBDIR)


def setup_textures():
    """ load the resource packs selected in game.  If none are found, load the
        textures from the games jar.
    """

    if path.exists(versions):
        load(archive)

    with open(settings) as f:
        for line in f:
            if line.startswith("resourcePacks:"):
                stack = eval(line.split(":")[1])
                if stack:
                    rp = path.join(MCPATH, "resourcepacks")

                    if path.exists(rp):
                        for pack in stack:
                            pack = path.join(rp, pack)
                            if path.exists(pack):
                                load(pack)
                            elif path.exists(path + ".zip"):
                                load(pack + ".zip")
                            else:
                                print("the pack could not be loaded")


def load(archive):
    """Take the archive file to be loaded into blender."""
    if os.path.exists(archive):
        with ZipFile(archive) as myzip:
            for file in myzip.namelist():
                fn = path.normpath(file) # Yes, I just did that
                if fn.startswith(textures) and fn.endswith(".png"):
                    myzip.extract(file, MBDIR)
                    if fn in bpy.data.images:
                        # Eventually add a way to remove duplicates, maybe just
                        # by replacing the image
                        pass
                    else:
                        bpy.data.images.load(os.sep.join([MBDIR,fn]))
                else:
                    if fn.startswith(states) and not fn.endswith("/"):
                        myzip.extract(file, MBDIR)
                    elif fn.startswith(models) and not fn.endswith("/"):
                        myzip.extract(file, MBDIR)
    else:
        print("pack not found")


def main():
    """Just runs load_textures()."""
    setup_textures()


if __name__ == '__main__':
    main()
