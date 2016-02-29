import pickle
import bpy
from enum import Enum


class Block():

    """This provides ability to create minecraft blocks in blender."""

    preview_location = (0, 0, 1.01)

    def __init__(self):
        name = ""
        colour = ()
        location = ()
        defs = {}
        self.load_defs()
        construct = None
        mesh = None

    def load_defs(self):
        """Loads the definitions of Minecaft block data values."""
        with open("blocks.pkl", "rb") as f:
            unpickle = pickle.Unpickler(f)
            self.defs = unpickle.load()

    def create_block(self, dvs, location=preview_location):
        "Create a block; anything that has an int location rather than float"
        self.name = self.find_name(dvs)
        location = location

        # if "slab" in name:
        #    ConstructType.half
        # elif "flower" in name:
        #    ConstructType.cross
        # else:
        #    ConstructType.block

        Material.diffuse(self, self.name)

    def uv_textures():
        return name + ".png"

    def find_name(self, dvs):
        dv1, dv2 = dvs
        return self.defs[dv1][dv2][0]


class Material():

    """Not yet implimented I'm not sure if its necessary."""

    group = bpy.data.node_groups.new(type="ShaderNodeTree", name="diffuse")

    group.inputs.new("NodeSocketColor", "Image")
    group.inputs.new("NodeSocketColor", "Alpha")
    input_node = group.nodes.new("NodeGroupInput")

    group.outputs.new("ShaderNodeBsdfDiffuse", "Out")
    output_node = group.nodes.new("NodeGroupOutput")

    diffuse = group.nodes.new(type="ShaderNodeBsdfDiffuse")
    trans = group.nodes.new(type="ShaderNodeBsdfTransparent")
    mix = group.nodes.new(type="ShaderNodeMixShader")
    mat = group.nodes.new(type="ShaderNodeOutputMaterial")

    group.links.new(input_node.outputs["Image"], diffuse.inputs[0])

    group.links.new(input_node.outputs["Alpha"], mix.inputs[0])

    group.links.new(diffuse.outputs[0], mix.inputs[2])

    group.links.new(trans.outputs[0], mix.inputs[1])

    group.links.new(mix.outputs[0], output_node.inputs[0])
    group.links.new(mix.outputs[0], mat.inputs[0])

    def diffuse(self, name):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        diffuse = mat.node_tree.nodes['Diffuse BSDF']
        group_node = mat.node_tree.nodes.new("ShaderNodeGroup")
        group_node.node_tree = Material.group
        tex = mat.node_tree.nodes.new(type="ShaderNodeTexImage")
        tex.image = bpy.data.images["stone_" +
                                    self.name.replace(" ", "_").lower() +
                                    ".png"]
        mat.node_tree.links.new(tex.outputs[0], group_node.inputs["Image"])
        mat.node_tree.links.new(tex.outputs[1], group_node.inputs["Alpha"])

    # wood = None
    # stone = None
    # glass = None


class ConstructType(Enum):

    def _block():
        bpy.ops.mesh.primitive_cube_add(radius=1,
                                        view_align=False,
                                        enter_editmode=False,
                                        location=Block.preview_location)

    def _cross():
        bpy.ops.mesh.primitive_plane_add(raduis=1,
                                         view_align=False,
                                         location=Block.preview_location)

    def _cross():
        pass

    def _stairs():
        pass

    def _fence():
        pass

    block = _block()
    cross = _cross()

    fence = _fence()
    stairs = _stairs()
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
