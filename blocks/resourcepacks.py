"""Handles the loading of resource packs."""

import bpy
import os
import sys

from os import path
from zipfile import ZipFile

if sys.platform == 'darwin':
    MCPATH = os.path.join(
        os.environ['HOME'], 'Library', 'Application Support', 'minecraft')
elif sys.platform == 'linux':
    MCPATH = os.path.join(os.environ['HOME'], '.minecraft')
else:
    MCPATH = os.path.join(os.environ['APPDATA'], '.minecraft')


def setup_textures():
    """ load the resource packs selected in game.  If none are found, load the
        textures from the games jar.
    """

    settings = path.join(MCPATH, "options.txt")
    versions = path.join(MCPATH, "versions")
    archive = path.sep.join([versions, "1.8", "1.8.jar"])

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
    if path.exists(archive):
        blockpath = path.sep.join(["assets",
                                   "minecraft",
                                   "textures",
                                   "blocks"])
        with ZipFile(archive) as myzip:
            for file in myzip.filelist:
                fn = file.filename  # Yes, I just did that.
                if fn.startswith(blockpath) and fn.endswith(".png"):
                    myzip.extract(file.filename, MCPATH)
                    two_paths = path.join(MCPATH + os.sep + fn)
                    bpy.data.images.load(two_paths)
    else:
        print("pack not found")


def main():
    """Just runs load_textures()."""
    setup_textures()

if __name__ == '__main__':
    main()
