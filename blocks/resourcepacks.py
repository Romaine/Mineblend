from zipfile import ZipFile
import os
import bpy


def load_textures(archive=None):
    MCPATH = os.path.join(os.environ['HOME'], '.minecraft')
    if not archive:
            versions = os.path.sep.join([MCPATH, "versions"])
            if os.path.exists(versions):
                archive = os.path.sep.join([versions, "1.8", "1.8.jar"])

    blockpath = os.path.sep.join(["assets",
                                  "minecraft",
                                  "textures",
                                  "blocks"])

    with ZipFile(archive) as myzip:
        for file in myzip.filelist:
            if file.filename.startswith(blockpath) and file.filename.endswith(".png"):
                myzip.extract(file.filename, MCPATH)
                two_paths = os.path.join(MCPATH + os.sep + file.filename)
                print(two_paths)
                bpy.data.images.load(two_paths)


def main():
    load_textures()

if __name__ == '__main__':
    main()
