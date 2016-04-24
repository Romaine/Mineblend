import bpy
import bmesh
import json
import os
import pickle
import pprint

from enum import Enum
from collections import defaultdict
from mathutils import Vector
from os import path

from Mineblend.sysutil import MCPATH
from Mineblend.blocks import resourcepacks


class Block():

    """This provides ability to create minecraft blocks in blender."""

    MBDIR = os.path.join(MCPATH, 'mineblend')

    if not os.path.exists(MBDIR):
        os.makedirs(MBDIR)

    preview_location = (0, 0, 1.01)
    models = {}

    assets = path.join(MBDIR, resourcepacks.assets)
    states = path.join(MBDIR, resourcepacks.states)
    textures = path.join(MBDIR, resourcepacks.textures)

    if not path.exists(textures):
        resourcepacks.setup_textures()

    models["item"] = {}
    models["block"] = {}
    for root, dirs, files in os.walk(path.join(MBDIR, resourcepacks.models)):
        if files:
            for file in files:
                model = path.join(root, file)
                models["block"][file] = {}
                with open(model) as f:
                    file = file.split(".")[0]
                    if root.split(os.sep)[-1] == "block":
                        models["block"][file] = json.load(f)
                    elif root.split(os.sep)[-1] == "item":
                        models["item"][file] = json.load(f)

    def __init__(self):
        self.name = ""
        self.colour = ()
        self.location = ()
        self.defs = {}
        self.load_defs()
        self.construct = None
        self.mesh = None
        self.material = None
        self.object = None
        self.model_stack = {}

    def load_defs(self):
        """Loads the definitions of Minecaft block data values."""
        with open(path.join(path.dirname(__file__), "../blocks.pkl"), "rb") as f:
            unpickle = pickle.Unpickler(f)
            self.defs = unpickle.load()

    def create_block(self, dvs, location=preview_location):
        "Create a block; anything that has an int location rather than float"
        self.name = self.find_name(dvs)
        self.location = location

        self.mesh = bpy.data.meshes.new('tempmesh')
        self.readState()
        self.generate_mesh()
        self.object = bpy.data.objects.new(self.name, self.mesh)
        Material.diffuse(self)

        self.object.name = self.name
        self.mesh.name = self.name
        self.object.active_material = self.material

        bpy.context.scene.objects.link(self.object)
        self.object.location = self.location

    def uv_textures(self, bm):
        bm.from_mesh(self.mesh)

        bm.loops.layers.uv.new()
        uv_layer = bm.loops.layers.uv[0]
        print(uv_layer)

        nFaces = len(bm.faces)
        print(nFaces)

        for face in bm.faces:
            face.loops[0][uv_layer].uv = (1, 1)
            face.loops[1][uv_layer].uv = (0, 1)
            face.loops[2][uv_layer].uv = (0, 0)
            face.loops[3][uv_layer].uv = (1, 0)

        bm.to_mesh(self.mesh)

    def readState(self):
        filepath = self.name.lower() + ".json"
        with open(path.join(Block.states, filepath)) as state:
            state = json.load(state)

        if "variants" in state:
            for variant in state["variants"]:
                model_filename = variant["model"]
                self.compile_model_stack(model_filename)

    def compile_model_stack(self, filename):
        filename = filename.split("/")[-1]
        if filename in Block.models["block"]:
            for k, v in Block.models["block"][filename].items():
                if k == "parent":
                    self.compile_model_stack(v)
                else:
                    if k in self.model_stack:
                        for k2, v2 in Block.models["block"][filename][k].items():
                            self.model_stack[k][k2] = v2
                    else:
                        self.model_stack[k] = v
                    print("model stack updated")

    def generate_mesh(self):

        elements = self.model_stack["elements"]
        for element in elements:
            bm = bmesh.new()
            vf = Vector(element["from"]) / 16
            vt = Vector(element["to"]) / 16

            x = 0
            y = 2
            z = 1

            one = bm.verts.new(Vector((vf[x], vf[y], -vf[z])))
            two = bm.verts.new(Vector((vf[x], vt[y], -vf[z])))
            three = bm.verts.new(Vector((vt[x], vt[y], -vf[z])))
            four = bm.verts.new(Vector((vt[x], vf[y], -vf[z])))

            five = bm.verts.new(Vector((vf[x], vf[y], -vt[z])))
            six = bm.verts.new(Vector((vf[x], vt[y], -vt[z])))
            seven = bm.verts.new(Vector((vt[x], vt[y], -vt[z])))
            eight = bm.verts.new(Vector((vt[x], vf[y], -vt[z])))

            down = bm.faces.new((seven, eight, five, six))
            up = bm.faces.new((three, two, one, four))
            north = bm.faces.new((two, three, seven, six))
            south = bm.faces.new((four, one, five, eight))
            west = bm.faces.new((one, two, six, five))
            east = bm.faces.new((three, four, eight, seven))

            self.uv_textures(bm)
            bm.to_mesh(self.mesh)

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

    def diffuse(self):
        mat = bpy.data.materials.new(self.name)
        mat.use_nodes = True
        # mat.node_tree.nodes['Diffuse BSDF']
        group_node = mat.node_tree.nodes.new("ShaderNodeGroup")
        group_node.node_tree = Material.group
        tex = mat.node_tree.nodes.new(type="ShaderNodeTexImage")
        # tex.image = bpy.data.images["stone_" +
        #                            self.name.replace(" ", "_").lower() +
        #                            ".png"]
        tex.image = bpy.data.images[self.name.replace(" ", "_").lower() +
                                    ".png"]
        tex.interpolation = "Closest"
        mat.node_tree.links.new(tex.outputs[0], group_node.inputs["Image"])
        mat.node_tree.links.new(tex.outputs[1], group_node.inputs["Alpha"])

        self.material = mat


def main():
    graniteblock = Block()
    dvs = [5, 2]
    graniteblock.create_block(dvs)
    print(graniteblock.name)
    print(graniteblock.model_stack)
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(graniteblock.model_stack)

if __name__ == '__main__':
    main()
