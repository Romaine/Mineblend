import bpy
import bmesh
import colorsys
import json
import os
import pprint

from mathutils import Vector
from os import path

from Mineblend.sysutil import MCPATH
from Mineblend.blocks import resourcepacks


class Block():

    """This provides ability to create minecraft blocks in blender."""

    MBDIR = os.path.join(MCPATH, 'mineblend')

    if not os.path.exists(MBDIR):
        os.makedirs(MBDIR)

    def_path = "ids.json"
    with open(path.join(path.dirname(__file__), def_path), "r") as f:
        defs = json.load(f)

    preview_location = (0, 0, 0)

    assets = path.join(MBDIR, resourcepacks.assets)
    states = path.join(MBDIR, resourcepacks.states)
    textures = path.join(MBDIR, resourcepacks.textures)

    models = {}
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
        self.bm = bmesh.new()

        self.name = ""
        self.name_ = ""
        self.blockstate = ""
        self.colour = ()
        self.location = ()
        self.construct = None
        self.mesh = None
        self.material = None
        self.object = None
        self.model_stack = {}
        self.verts = {}
        self.faces = []
        self.dvs = ()

    def vert_map(element):
        vf = Vector(element["from"]) / 16
        vt = Vector(element["to"]) / 16

        x = 0
        y = 2
        z = 1

        verts = {
            "one": Vector((vf[x], -vf[y], vf[z])),

            "two": Vector((vf[x], -vt[y], vf[z])),

            "three": Vector((vt[x], -vt[y], vf[z])),

            "four": Vector((vt[x], -vf[y], vf[z])),

            "five": Vector((vf[x], -vf[y], vt[z])),

            "six": Vector((vf[x], -vt[y], vt[z])),

            "seven": Vector((vt[x], -vt[y], vt[z])),

            "eight": Vector((vt[x], -vf[y], vt[z])),
        }

        return verts

    face_map = {
        "up": ("eight", "five", "six", "seven"),
        "down": ("four", "one", "two", "three"),
        "north": ("two", "three", "seven", "six"),
        "south": ("four", "one", "five", "eight"),
        "east": ("one", "two", "six", "five"),
        "west": ("three", "four", "eight", "seven")
    }

    def create_block(self, dvs=None, location=preview_location):
        "Create a block; anything that has an int location rather than float"
        self.location = location
        self.dvs = dvs
        self.find_name(dvs)

        self.mesh = bpy.data.meshes.new('tempmesh')
        self.readState()

        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(self.model_stack)

        textures = self.model_stack["textures"]

        if textures:
            self.textures = textures
        else:
            return
            # Deal with liquid problem

        self.generate_mesh()
        self.finalise()
        return self.mesh

    def find_name(self, dvs):
        dv1, dv2 = dvs
        # print(dv1, dv2)
        for block in self.defs:
            if block["type"] == dv1:
                if block["meta"] == dv2:
                    self.name = block["name"]
                    self.name_ = self.name.replace(" ", "_").lower()
                    self.blockstate = block["blockstate"]

    def to_path(self, pointer):
        """Converts a path name or tag to the name"""
        if pointer.startswith("#"):
            return self.to_path(self.textures[pointer[1:]])
        else:
            return pointer

    def materials(self):
        mat = None
        material = Material()
        for i, v in enumerate(self.textures.values()):
            if not v.startswith("#"):
                name = self.to_path(v).split("/")[-1]

                if not name.split(".")[0] in bpy.data.materials:
                    mat = material.diffuse(self, name)
                else:
                    mat = bpy.data.materials[name]

                if not self.mesh.materials:
                    self.mesh.materials.append(mat)
                else:
                    self.mesh.materials.append(mat)

    def sort_textures(self):
        elements = self.model_stack["elements"]

        # UV's

        self.bm.loops.layers.uv.new()
        uv_layer = self.bm.loops.layers.uv[0]

        # Assign materials to respective faces.
        print("Textures", self.textures)

        for tag in Block.face_map.keys():
            if tag not in self.textures.keys():
                if "side" in self.textures:
                    self.textures["east"] = self.textures["side"]
                    self.textures["west"] = self.textures["side"]
                    self.textures["north"] = self.textures["side"]
                    self.textures["south"] = self.textures["side"]

                self.textures["up"] = self.textures["top"]
                self.textures["down"] = self.textures["bottom"]

                # del self.textures["side"]
                # del self.textures["top"]
                # del self.textures["bottom"]

        for element in elements:
            face_data = element["faces"]

            for face, data in face_data.items():

                texture = self.to_path(data["texture"])

                for box in self.faces:
                    for facemesh in box[face]:

                        #  Commence MLG UV foo
                        if "uv" in data:
                            # print(uv)
                            x1, y1, x2, y2 = 1 / 16 * Vector(data["uv"])
                            facemesh.loops[0][uv_layer].uv = (x1, y1)
                            facemesh.loops[1][uv_layer].uv = (x2, y1)
                            facemesh.loops[2][uv_layer].uv = (x2, y2)
                            facemesh.loops[3][uv_layer].uv = (x1, y2)
                        else:
                            facemesh.loops[0][uv_layer].uv = (0, 0)
                            facemesh.loops[1][uv_layer].uv = (1, 0)
                            facemesh.loops[2][uv_layer].uv = (1, 1)
                            facemesh.loops[3][uv_layer].uv = (0, 1)

        for i, mat in enumerate(self.mesh.materials):
            for face, data in element["faces"].items():
                texture = self.to_path(data["texture"])
                if data["texture"] == "#overlay":
                    # skip
                    pass

                if mat.name.split(".")[0] == texture.split("/")[1]:
                    for face in box[face]:
                        face.material_index = i

        # @TODO Stop images of the same name from overwriting eachother
        #       by prepending their path.

    def readState(self):
        # print(self.name)
        filepath = path.join(Block.states, self.name_ + ".json")
        if not path.exists(filepath):
            filepath = path.join(Block.states, self.blockstate + ".json")
            if not path.exists(filepath):
                self.liquid()
                if self.dvs[0] in [8, 9, 10, 11]:
                    self.compile_model_stack("cube_all")
                    self.textures.append()
                    return
                else:
                    print("No blockstate file for", "Name:", self.name, "dataid", self.dvs)

        with open(filepath) as state:
            state = json.load(state)

        if "variants" in state:
            for variant in state["variants"].values():
                if isinstance(variant, dict):
                    print("variant", variant["model"])
                    model_filename = variant["model"]

                else:
                    print("variant", variant[0]["model"])
                    model_filename = variant[0]["model"]
        else:
            for part in state["multipart"]:
                if isinstance(part, dict):
                    # print("variant", part["model"])
                    model_filename = part["model"]
                else:
                    pass  # print("variant", variant[0]["model"])

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

    def liquid(self):
        pass

    def generate_mesh(self, to_draw=None, offset=Vector([0] * 3)):
        # @TODO Impliment rotation to support; planar meshes particularly.
        elements = self.model_stack["elements"]

        bm = self.bm

        if not len(self.bm.verts) % 500:
            print(self.name, "verts", len(self.bm.verts))

        for i, element in enumerate(elements):
            vert_map = Block.vert_map(element)
            vert_map.update((k, v + offset) for k, v in vert_map.items())

            for face in Block.face_map.keys():
                if not to_draw:
                    to_draw = element["faces"]

            for face, present in to_draw.items():
                if present:
                    if not len(self.faces) >= i+1:
                        self.faces.append({})
                    if face not in self.faces[i]:
                        self.faces[i][face] = []

                    self.faces[i][face].append(bm.faces.new(bm.verts.new(vert_map[vert]) for vert in Block.face_map[face]))


                    # currently not working
                    # self.faces[face].append(bm.faces.new([self.verts[vert_map[vert].freeze()] for vert in Block.face_map[face]]))

    def finalise(self):
        self.materials()
        self.sort_textures()
        self.bm.to_mesh(self.mesh)
        self.object = bpy.data.objects.new(self.name, self.mesh)

        self.object.name = self.name
        self.mesh.name = self.name

        bpy.context.scene.objects.link(self.object)


class Material():

    """Not yet implimented I'm not sure if its necessary."""

    def __init__(self):

        self.group = bpy.data.node_groups.new(
            type="ShaderNodeTree", name="diffuse")

        self.group.inputs.new("NodeSocketColor", "Image")
        self.group.inputs.new("NodeSocketColor", "Alpha")
        input_node = self.group.nodes.new("NodeGroupInput")

        self.group.outputs.new("ShaderNodeBsdfDiffuse", "Out")
        output_node = self.group.nodes.new("NodeGroupOutput")

        diffuse = self.group.nodes.new(type="ShaderNodeBsdfDiffuse")
        trans = self.group.nodes.new(type="ShaderNodeBsdfTransparent")
        mix = self.group.nodes.new(type="ShaderNodeMixShader")
        mat = self.group.nodes.new(type="ShaderNodeOutputMaterial")

        self.group.links.new(input_node.outputs["Image"], diffuse.inputs[0])
        self.group.links.new(input_node.outputs["Alpha"], mix.inputs[0])
        self.group.links.new(diffuse.outputs[0], mix.inputs[2])
        self.group.links.new(trans.outputs[0], mix.inputs[1])
        self.group.links.new(mix.outputs[0], output_node.inputs[0])
        self.group.links.new(mix.outputs[0], mat.inputs[0])

    def diffuse(self, block, image_name=False):
        # print("starting diffuse")
        mat = bpy.data.materials.new(block.to_path(image_name))
        mat.use_nodes = True
        # mat.node_tree.nodes['Diffuse BSDF']
        group_node = mat.node_tree.nodes.new("ShaderNodeGroup")
        group_node.node_tree = self.group
        tex = mat.node_tree.nodes.new(type="ShaderNodeTexImage")

        tex.image = bpy.data.images[image_name + ".png"]
        tex.interpolation = "Closest"
        mat.node_tree.links.new(tex.outputs[0], group_node.inputs["Image"])
        mat.node_tree.links.new(tex.outputs[1], group_node.inputs["Alpha"])

        # My terrible grudge against simplified (US) english can be seen ahead!
        p = list(tex.image.pixels)

        R = p[slice(0, -1, 4)]
        G = p[slice(1, -1, 4)]
        B = p[slice(2, -1, 4)]
        A = p[slice(3, -1, 4)]

        hsv = [colorsys.rgb_to_hsv(r, g, b) for r, g, b in list(zip(R, G, B))]

        def mean(v): return float(sum(v)) / len(v) if len(v) else 0

        hue, sat, val = zip(*hsv)
        saturation = mean(sat) if sum(R) == sum(G) == sum(B) else 1
        mean_colour = colorsys.hsv_to_rgb(mean(hue), saturation, mean(val))

        mat.diffuse_color = mean_colour  # for solid viewport

        #print("end of diffuse")

        return mat


class BlockCluster(Block):

    """Reimplimentation of what mineways gives us."""

    def __init__(self, options):
        super().__init__()
        self.options = options
        loadRadius = 2
        numElements = (loadRadius * 2 + 1) * 16  # chunks * blocks
        self.yMax = options['highlimit']
        self.yMin = options['lowlimit']
        self.xMin = 0
        self.xMax = numElements - 1
        self.zMax = numElements - 1
        self.zMin = 0
        print(self.verts)

    def sides(self, blocks, location):
        """Return a list of tuples; Block ID and data.
            [up, down, north, south, east, west]"""

        BC = BlockCluster

        faces = {
            "up": False,
            "down": False,
            "north": False,
            "south": False,
            "east": False,
            "west": False
        }

        x, y, z = location

        block_id = blocks[0][x][y][z]

        if y != self.yMax:
            if blocks[0][x][y + 1][z] != block_id:  # up
                faces["up"] = True

        if y != 0:
            if blocks[0][x][y - 1][z] != block_id:  # down
                faces["down"] = True

        if z != 0:
            if blocks[0][x][y][z - 1] != block_id:  # north
                faces["north"] = True

        if z != self.zMax:
            if blocks[0][x][y][z + 1] != block_id:  # south
                faces["south"] = True

        if x != self.xMax:
            if blocks[0][x + 1][y][z] != block_id:  # east
                faces["east"] = True

        if x != 0:
            if blocks[0][x - 1][y][z] != block_id:  # west
                faces["west"] = True

        return faces

    def create_cluster(self, blocks):

        clusters = {}
        i = 0
        for x in range(self.zMin, self.xMax):
            for y in range(self.yMin, self.yMax):
                for z in range(self.xMin, self.zMax):
                    block_id = blocks[0][x][y][z]
                    if block_id not in [0, 166, 8, 9, 10, 11]:
                        sides = self.sides(blocks, (x, y, z))  # Make a generator?
                        if True in sides.values():
                            dvs = (blocks[0][x][y][z], blocks[1][x][y][z])

                            print(dvs)

                            if block_id not in clusters:
                                clusters[block_id] = BlockCluster(self.options)
                                clusters[block_id].cluster(dvs)

                            clusters[block_id].generate_mesh(sides, Vector((x, z, y)))  # The second parameter determines the orientation of the terrain outputted.

                            if not i % 100:
                                print("total blocks processed", i)
                            i += 1

        for cluster in clusters:
            clusters[cluster].finalise()

    def cluster(self, dvs):
        print("finding name")
        self.find_name(dvs)
        print("name is ", self.name)

        print("creating a new mesh")
        self.mesh = bpy.data.meshes.new("cluster_" + self.name_)

        print("reading state")
        self.readState()
        print("setting textures")
        self.textures = self.model_stack["textures"]


def main():
    graniteblock = Block()
    dvs = [2, 0]
    graniteblock.create_block(dvs)
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(graniteblock.model_stack)

if __name__ == '__main__':
    main()
