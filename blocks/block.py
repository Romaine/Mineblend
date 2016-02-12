import pickle
from enum import Enum
import bpy


class Block():

    """This provides ability to create minecraft blocks in blender."""

    preview_location = (0, 0, 1.01)

    def __init__(self):
        self.name = ""
        self.colour = ()
        self.location = ()
        self.defs = {}
        self.load_defs()
        self.construct = None

    def load_defs(self):
        """Loads the definitions of Minecaft block data values."""
        with open("blocks.pkl", "rb") as f:
            unpickle = pickle.Unpickler(f)
            defs = unpickle.load()
            self.defs = defs

    def create_block(self, dvs, location=preview_location):
        "Create a block; anything that has an int location rather than float"
        self.name = self.find_name(dvs)
        self.location = location

        if "slab" in self.name:
            ConstructType.half
        elif "flower" in self.name:
            ConstructType.cross
        else:
            ConstructType.block

    def find_textures():
        bpy.data.images.

    def find_name(self, dvs):
        dv1, dv2 = dvs
        return self.defs[dv1][dv2][0]


class material(Enum):

    """Not yet implimented I'm not sure if its necessary."""

    wood = None
    stone = None
    wool = None
    glass = None


class ConstructType(Enum):

    def _block():
            bpy.ops.mesh.primitive_cube_add(radius=1,
                                            view_align=False,
                                            enter_editmode=False,
                                            location=Block.preview_location)

    block = _block()

    # cross
    # fence
    # stairs
    # special


def main():
    graniteblock = Block()
    dvs = [1, 1]
    graniteblock.create_block(dvs)
    print(graniteblock.name)

if __name__ == '__main__':
    main()
