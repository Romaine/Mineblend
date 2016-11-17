# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# Contributors:
# Originally authored by Acro
# Modified by Phil B
#
#
#
# Acro's Python3.2 NBT Reader for Blender Importing Minecraft

# TODO Possible Key Options for the importer:

# TODO: load custom save locations, rather than default saves folder.
# good for backup/server game reading.
# what's a good way to swap out the world-choice dialogue for a custom
# path input??

#"Surface only": use the heightmap and only load surface.
# Load more than just the top level, obviously, cos of cliff
# walls, caves, etc. water should count as transparent for this process,
# as should glass, flowers, torches, portal; all nonsolid block types.

#"Load horizon" / "load radius": should be circular, or have options

import bpy

from bpy.props import FloatVectorProperty
from mathutils import Vector
from .block import Block, BlockCluster
import numpy as npy
# from Mineblend import blockbuild
from . import MCPATH, MCSAVEPATH
# using blockbuild.createMCBlock(mcname, diffuseColour, mcfaceindices)
# faceindices order: (bottom, top, right, front, left, back)
# NB: this should probably change, as it was started by some uv errors.

from . import *
# level.dat, .mcr McRegion, .mca Anvil: all different formats, but all are NBT.

import sys
import os
import gzip
import datetime


REPORTING = {}
REPORTING['totalchunks'] = 0
totalchunks = 0
wseed = None  # store chosen world's worldseed, handy for slimechunk calcs.

MCREGION_VERSION_ID = 0x4abc
    # Check world's level.dat 'version' property for these.
ANVIL_VERSION_ID = 0x4abd
#

# TODO: Retrieve these from bpy.props properties stuck in the scene RNA.
EXCLUDED_BLOCKS = [1, 3, 87]
    # (1,3,87) # hack to reduce loading / slowdown: (1- Stone, 3- Dirt, 87 netherrack). Other usual suspects are Grass,Water, Leaves, Sand,StaticLava

LOAD_AROUND_3D_CURSOR = False  # calculates 3D cursor as a Minecraft world position, and loads around that instead of player (or SMP world spawn) position

unknownBlockIDs = set()

OPTIONS = {}

#"Profile" execution checks for measuring whether optimisations are worth it:

REPORTING['blocksread'] = 0
REPORTING['blocksdropped'] = 0
t0 = datetime.datetime.now()
tReadAndBuffered = -1
tToMesh = -1
tChunk0 = - \
    1  # these don't need to be globals - just store the difference in the arrays.
tChunkEnd = -1
tRegion0 = -1
tRegionEnd = -1
tChunkReadTimes = []
tRegionReadTimes = []

WORLD_ROOT = None

# MCBINPATH -- in /bin, zipfile open minecraft.jar, and get terrain.png.
# Feed directly into Blender, or save into the Blender temp dir, then import.
print("Mineblend saved games location: " + MCPATH)


def readLevelDat():
    """Reads the level.dat for info like the world name, player inventory..."""
    lvlfile = gzip.open('level.dat', 'rb')

    # first byte must be a 10 (TAG_Compound) containing all else.
    # read a TAG_Compound...
    # rootTag = Tag(lvlfile)

    rootTag = TagReader.readNamedTag(lvlfile)[
        1]  # don't care about the name... or do we? Argh, it's a named tag but we throw the blank name away.

    print(rootTag.printTree(0))  # give it repr with an indent param...?


def readRegion(fname, vertexBuffer):
    # A region has an 8-KILObyte header, of 1024 locations and 1024 timestamps.
    # Then from 8196 onwards, it's chunk data and (arbitrary?) gaps.
    # Chunks are zlib compressed & have their own structure, more on that later.
    print('== Reading region %s ==' % fname)

    rfile = open(fname, 'rb')
    regionheader = rfile.read(8192)

    chunklist = []
    chunkcount = 0
    cio = 0  # chunk index offset
    while cio + 4 <= 4096:  # only up to end of the locations! (After that is timestamps)
        cheadr = regionheader[cio:cio + 4]
        # 3 bytes "offset"         -- how many 4kiB disk sectors away the chunk data is from the start of the file.
        # 1 byte "sector count"    -- how many 4kiB disk sectors long the chunk data is.
        #(sector count is rounded up during save, so gives the last disk sector in which there's data for this chunk)

        offset = unpack(">i", b'\x00' + cheadr[0:3])[0]
        chunksectorcount = cheadr[
            3]  # last of the 4 bytes is the size (in 4k sectors) of the chunk

        chunksLoaded = 0
        if offset != 0 and chunksectorcount != 0:  # chunks not generated as those coordinates yet will be blank!
            chunkdata = readChunk(rfile, offset, chunksectorcount)
                                  # TODO Make sure you seek back to where you
                                  # were to start with ...
            chunksLoaded += 1
            chunkcount += 1

            chunklist.append((offset, chunksectorcount))

        cio += 4

    rfile.close()

    print("Region file %s contains %d chunks." % (fname, chunkcount))
    return chunkcount


def toChunkPos(pX, pZ):
    return (pX / 16, pZ / 16)


def batchBuild(meshBuffer):
    # build all geom from pydata as meshes in one shot. :) This is fast.
    for meshname in (meshBuffer.keys()):
        me = bpy.data.meshes[meshname]
        me.from_pydata(meshBuffer[meshname], [], [])
        me.update()


def mcToBlendCoord(chunkPos, blockPos):
    """Converts a Minecraft chunk X,Z pair and a Minecraft ordered X,Y,Z block
location triple into a Blender coordinate vector Vx,Vy,Vz.
Just remember: in Minecraft, Y points to the sky."""

    # Mapping Minecraft coords -> Blender coords
    # In Minecraft, +Z (west) <--- 0 ----> -Z (east), while North is -X and South is +X
    # In Blender, north is +Y, south is-Y, west is -X and east is +X.
    # So negate Z and map it as X, and negate X and map it as Y. It's slightly
    # odd!

    vx = -(chunkPos[1] << 4) - blockPos[2]
    vy = -(chunkPos[0] << 4) - blockPos[0]
           # -x of chunkpos and -x of blockPos (x,y,z)
    vz = blockPos[1]  # Minecraft's Y.

    return Vector((vx, vy, vz))


def getMCBlockType(blockID, extraBits):
    """Gets reference to a block type mesh, or creates it if it doesn't exist.
The mesh created depends on meshType from the global blockdata (whether it's torch or repeater, not a cube)
These also have to be unique and differently named for directional versions of the same thing - eg track round a corner or up a slope.
This also ensures material and name are set."""

    if not usesExtraBits:  # quick early create...
        landmeshname = "".join(["mc", corename])
        if landmeshname in bpy.data.meshes:
            return bpy.data.meshes[landmeshname]
        else:
            extraBits = None

    nameVariant = ''
    if blockID in BLOCKVARIANTS:
        variants = BLOCKVARIANTS[blockID]
        if extraBits is not None and extraBits >= 0 and extraBits < len(variants):
            # FIXME - why?
            # print(str(extraBits))
            extraBits = int(extraBits)
            variantData = variants[extraBits]
            if len(variantData) > 0:
                nameVariant = variantData[0]
                # print("%d Block uses extra data: {%d}. So name variant is: %s" % (blockID, extraBits, nameVariant))
                # Now apply each available variant datum: RGB triple, texture
                # faces, and blockbuild variation.
                if len(variantData) > 1:  # read custom RGB
                    colourtriple = variantData[1]
                    if len(variantData) > 2:
                        mcfaceindices = variantData[2]
                        # mesh constructor...
    corename = "".join([corename, nameVariant])
    meshname = "".join(["mc", corename])

    block = Block()

    blockname = dupblock.name
    landmeshname = "".join(["mc", blockname.replace('Block', '')])

    if landmeshname in bpy.data.meshes:
        return bpy.data.meshes[landmeshname]

    landmesh = bpy.data.meshes.new(landmeshname)
    landob = bpy.data.objects.new(landmeshname, landmesh)
    bpy.context.scene.objects.link(landob)

    global WORLD_ROOT  # Will have been inited by now. Parent the land to it. (a bit messy, but... meh)
    landob.parent = WORLD_ROOT
    dupblock.parent = landob
    landob.dupli_type = "VERTS"
    return landmesh


def slimeOn():
    """Creates the cloneable slime block (area marker) and a mesh to duplivert it."""
    if 'slimeChunks' in bpy.data.objects:
        return

    # Create cube! (maybe give it silly eyes...)
    # ensure 3d cursor at 0...

    bpy.ops.mesh.primitive_cube_add()
    slimeOb = bpy.context.object  # get ref to last created ob.
    slimeOb.name = 'slimeMarker'
    # Make it chunk-sized. It starts 2x2x2
    bpy.ops.transform.resize(value=(8, 8, 8))
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    # create material for the markers
    slimeMat = None
    smname = "mcSlimeMat"
    if smname in bpy.data.materials:
        slimeMat = bpy.data.materials[smname]
    else:
        slimeMat = bpy.data.materials.new(smname)
        # FIXME - hard code color
        slimeMat.diffuse_color = [86 / 256.0, 139.0 / 256.0, 72.0 / 256.0]
        slimeMat.diffuse_shader = 'OREN_NAYAR'
        slimeMat.diffuse_intensity = 0.8
        slimeMat.roughness = 0.909
        # slimeMat.use_shadeless = True	#traceable false!
        slimeMat.use_transparency = True
        slimeMat.alpha = .25

    slimeOb.data.materials.append(slimeMat)
    slimeChunkmesh = bpy.data.meshes.new("slimeChunks")
    slimeChunkob = bpy.data.objects.new("slimeChunks", slimeChunkmesh)
    bpy.context.scene.objects.link(slimeChunkob)
    slimeOb.parent = slimeChunkob
    slimeChunkob.dupli_type = "VERTS"
    global WORLD_ROOT
    slimeChunkob.parent = WORLD_ROOT


def batchSlimeChunks(slimes):
    "Populate all slime marker centres into the dupli-geom from pydata."
    me = bpy.data.meshes["slimeChunks"]
    me.from_pydata(slimes, [], [])
    me.update()


def getWorldSelectList():
    worldList = []
    if os.path.exists(MCSAVEPATH):
        startpath = os.getcwd()
        os.chdir(MCSAVEPATH)
        saveList = os.listdir()
        saveFolders = [f for f in saveList if os.path.isdir(f)]
        wcount = 0
        for sf in saveFolders:
            if os.path.exists(sf + "/level.dat"):
                # Read the actual world name (not just folder name)
                wData = None
                try:
                    with gzip.open(sf + '/level.dat', 'rb') as levelDat:
                        wData = readNBT(levelDat)
                        # catch errors if level.dat wasn't a gzip...
                except IOError:
                    print("Unknown problem with level.dat format for %s" % sf)
                    continue

                # FIXME - having a problem
                try:
                    if 'LevelName' in wData.value['Data'].value:
                        wname = wData.value['Data'].value['LevelName'].value
                    else:
                        wname = "<no name>"

                    wsize = wData.value['Data'].value['SizeOnDisk'].value
                    readableSize = "(%0.1f)" % (wsize / (1024 * 1024))
                    worldList.append((sf, sf, wname + " " + readableSize))
                    wcount += 1
                except KeyError:
                    print("key not found in %s" % wData.value['Data'])
        os.chdir(startpath)

    if worldList != []:
        return worldList
    else:
        return None


def hasNether(worldFolder):
    if worldFolder == "":
        return False
    worldList = []
    if os.path.exists(MCSAVEPATH):
        worldList = os.listdir(MCSAVEPATH)
        if worldFolder in worldList:
            wp = os.path.join(MCSAVEPATH, worldFolder, 'DIM-1')
            return os.path.exists(wp)
            # and: contains correct files? also check regions aren't empty.
    return False


def hasEnd(worldFolder):
    if worldFolder == "":
        return False
    worldList = []
    if os.path.exists(MCSAVEPATH):
        worldList = os.listdir(MCSAVEPATH)
        if worldFolder in worldList:
            wp = os.path.join(MCSAVEPATH, worldFolder, 'DIM1')
            return os.path.exists(wp)
            # and: contains correct files? also check regions aren't empty.
    return False


def readMinecraftWorld(self, worldFolder, loadRadius, toggleOptions):
    global unknownBlockIDs, wseed
    global EXCLUDED_BLOCKS
    global WORLD_ROOT
    global OPTIONS, REPORTING
    OPTIONS = toggleOptions

    # timing/profiling:
    global tChunkReadTimes

    if worldFolder == "":
        # World selected was blank. No saves. i.e. only when world list is empty
        print("No valid saved worlds were available to load.")
        return

    if not OPTIONS['omitstone']:
        EXCLUDED_BLOCKS = []

    worldList = []

    if os.path.exists(MCSAVEPATH):
        worldList = os.listdir(MCSAVEPATH)
        # print("MC Path exists! %s" % os.listdir(MCPATH))
        # wherever os was before, save it, and restore it after this completes.
        os.chdir(MCSAVEPATH)

    worldSelected = worldFolder

    os.chdir(os.path.join(MCSAVEPATH, worldSelected))

    # If there's a folder DIM-1 in the world folder, you've been to the Nether!
    # ...And generated Nether regions.
    if os.path.exists('DIM-1'):
        if OPTIONS['loadnether']:
            print('nether LOAD!')
        else:
            print('Nether is present, but not chosen to load.')

    if os.path.exists('DIM1'):
        if OPTIONS['loadend']:
            print('load The End...')
        else:
            print('The End is present, but not chosen to load.')

    # if the player didn't save out in those dimensions, we HAVE TO load at 3D
    # cursor (or 0,0,0)

    worldData = None
    pSaveDim = None
    worldFormat = 'mcregion'  # assume initially

    with gzip.open('level.dat', 'rb') as levelDat:
        worldData = readNBT(levelDat)
    # print(worlddata.printTree(0))

    # Check if it's a multiplayer saved game (that's been moved into saves dir)
    # These don't have the Player tag.
    if 'Player' in worldData.value['Data'].value:
        # It's singleplayer
        pPos = [posFloat.value for posFloat in worldData.value['Data'].value[
            'Player'].value['Pos'].value]  # in NBT, there's a lot of value...
        pSaveDim = worldData.value['Data'].value[
            'Player'].value['Dimension'].value
        print('Player: ' + str(pSaveDim) + ', ppos: ' + str(pPos))
    else:
        # It's multiplayer.
        # Get SpawnX, SpawnY, SpawnZ and centre around those. OR
        # TODO: Check for another subfolder: 'players'. Read each NBT .dat in
        # there, create empties for all of them, but load around the first one.
        spX = worldData.value['Data'].value['SpawnX'].value
        spY = worldData.value['Data'].value['SpawnY'].value
        spZ = worldData.value['Data'].value['SpawnZ'].value
        pPos = [float(spX), float(spY), float(spZ)]

        # create empty markers for each player.
        # and: could it load multiplayer nether/end based on player loc?

    if 'version' in worldData.value['Data'].value:
        fmtVersion = worldData.value['Data'].value['version'].value
        # 19133 for Anvil. 19132 is McRegion.
        if fmtVersion == MCREGION_VERSION_ID:
            print("World is in McRegion format")
        elif fmtVersion == ANVIL_VERSION_ID:
            print("World is in Anvil format")
            worldFormat = "anvil"

    wseed = worldData.value['Data'].value['RandomSeed'].value  # it's a Long
    print("World Seed : %d" % (wseed))  # or self.report....

    # NB: we load at cursor if player location undefined loading into Nether
    if OPTIONS['atcursor'] or (OPTIONS['loadnether'] and (pSaveDim is None or int(pSaveDim) != -1)):
        cursorPos = bpy.context.scene.cursor_location
        # that's an x,y,z vector (in Blender coords)
        # convert to insane Minecraft coords! (Minecraft pos = -Y, Z, -X)
        pPos = [-cursorPos[1], cursorPos[2], -cursorPos[0]]

    if OPTIONS['loadnether']:
        os.chdir(os.path.join("DIM-1", "region"))
    elif OPTIONS['loadend']:
        os.chdir(os.path.join("DIM1", "region"))
    else:
        os.chdir("region")

    meshBuffer = {}
    blockBuffer = {}

    # Initialise the world root - an empty to parent all land objects to.
    WORLD_ROOT = bpy.data.objects.new(worldSelected, None)  # ,None => EMPTY!
    bpy.context.scene.objects.link(WORLD_ROOT)
    WORLD_ROOT.empty_draw_size = 2.0
    WORLD_ROOT.empty_draw_type = 'SPHERE'

    regionfiles = []
    regionreader = None
    worldFormat == 'anvil'

    from .mcanvilreader import AnvilChunkReader
    regionreader = AnvilChunkReader()

    # except when loading nether...
    playerChunk = toChunkPos(pPos[0], pPos[2])  # x, z

    print("Loading %d blocks around centre." % loadRadius)
    # loadRadius = 10 #Sane amount: 5 or 4.

    if not OPTIONS['atcursor']:  # loading at player
        # Add an Empty to show where the player is. (+CENTRE CAMERA ON!)
        playerpos = bpy.data.objects.new('PlayerLoc', None)
        # set its coordinates...
        # convert Minecraft coordinate position of player into Blender coords:
        playerpos.location[0] = -pPos[2]
        playerpos.location[1] = -pPos[0]
        playerpos.location[2] = pPos[1]
        bpy.context.scene.objects.link(playerpos)
        playerpos.parent = WORLD_ROOT

    # total chunk count across region files:
    REPORTING['totalchunks'] = 0

    pX = int(playerChunk[0])
    pZ = int(playerChunk[1])

    print('Loading a square halfwidth of %d chunks around load position, so creating chunks: %d,%d to %d,%d' %
          (loadRadius, pX - loadRadius, pZ - loadRadius, pX + loadRadius, pZ + loadRadius))

    if (OPTIONS['showslimes']):
        slimeOn()
        from . import slimes
        slimeBuffer = []

    # FIXME - need deltaX/Y/Z to get array index
    zeroAdjX = -1 * (pX - loadRadius)
    zeroAdjZ = -1 * (pZ - loadRadius)
    # zeroAdjY = -1 * OPTIONS['lowlimit']
    # sizeY = OPTIONS['highlimit']-OPTIONS['lowlimit']+1
    sizeY = 256

    # for newVoxel and other approaches that process the entire world section
    # as a whole
    numElements = (loadRadius * 2 + 1) * 16  # chunks * blocks
    # numElements=(loadRadius*2)*16 # chunks * blocks
    # print("block buffer size: "+str(numElements)+", "+str(sizeY)+",
    # "+str(numElements))
    print("block buffer size: " + str(numElements)
          + ", " + str(sizeY) + ", " + str(numElements))
    blockBuffer = npy.zeros((numElements, sizeY, numElements))
    extraBuffer = npy.zeros((numElements, sizeY, numElements))

    wm = bpy.context.window_manager
    wm.progress_begin(0, 99)
    progCounter = 0
    progMax = (pZ + loadRadius + 1) - (pZ - loadRadius)
    for z in range(pZ - loadRadius, pZ + loadRadius + 1):
        wm.progress_update(((progCounter / progMax) / 2) * 100)
        progCounter += 1
        for x in range(pX - loadRadius, pX + loadRadius + 1):

            tChunk0 = datetime.datetime.now()
            # print('processing '+str(x)+', '+str(z))
            if (OPTIONS['newVoxel']):  # new method

                # FIXME - currently only supported by anvil reader
                # regionreader.processChunk2(x,z, blockBuffer, zeroAdjX,
                # zeroAdjY, zeroAdjZ)
                regionreader.processChunk2(
                    x, z, blockBuffer, extraBuffer, zeroAdjX, zeroAdjZ)

    if (OPTIONS['showslimes']):
        if slimes.isSlimeSpawn(wseed, x, z):
            slimeLoc = mcToBlendCoord((x, z), (8, 8, 8))  # (8,8,120)
            slimeLoc += Vector((0.5, 0.5, -0.5))
            slimeBuffer.append(slimeLoc)
    shouldHollow = OPTIONS['hollow']
    if (OPTIONS['newVoxel']):  # new method for voxel-based
        yMax = OPTIONS['highlimit']
        yMin = OPTIONS['lowlimit']
        xMin = 0
        xMax = numElements - 1
        zMin = 0
        zMax = numElements - 1
        hideSides = OPTIONS['hideSides']
        print('mMin/Max: ' + str(xMin) + '-' + str(xMax) + ', yMin/Max: ' +
              str(yMin) + '-' + str(yMax) + ', zMin/Max: ' + str(zMin) + '-' + str(zMax))
        if hideSides:
            print("hiding sides")
        progMax = (zMax + 1) - zMin
        progCounter = 0

        defs = Block.defs

        for z in range(zMin, zMax + 1):
            wm.progress_update((49 + (progCounter / progMax) / 2) * 100)
            progCounter += 1

            for y in range(yMin, yMax + 1):  # FIXME - 0,255? (i.e. yMin/Max for visibility only?)
                for x in range(xMin, xMax + 1):
                    blockID = blockBuffer[x][y][z]
                    skipBlock = False
                    # if ((x>0) & (y>yMin) & (z>0) & (x<numElements) & (y<yMax)
                    # & (z<numElements)):
                    if shouldHollow:
                        if ((x > xMin) & (y > yMin) & (z > zMin) & (x < xMax) & (y < yMax) & (z < zMax)):
                            if (blockID in (defs[8], defs[9])):
                                print("is water")
                                if blockSurroundedBy(blockBuffer, BLOCKS_WATER, x, y, z):
                                    print("hollowing")
                                    blockBuffer[x][y][z] = -1 * blockID
                                    REPORTING['blocksdropped'] += 1
                                    skipBlock = True
                            elif (blockID in (defs[10], defs[11])):
                                if blockSurroundedBy(blockBuffer, BLOCKS_LAVA, x, y, z):
                                    blockBuffer[x][y][z] = -1 * blockID
                                    REPORTING['blocksdropped'] += 1
                                    skipBlock = True
                            elif (False):
                                if blockSurroundedBy(blockBuffer, BLOCKS_OTHER, x, y, z):
                                    blockBuffer[x][y][z] = -1 * blockID
                                    REPORTING['blocksdropped'] += 1
                                    skipBlock = True
                    if (hideSides):
                        if ((x == xMin) | (x == xMax) | (y == yMin) | (y == yMax) | (z == zMin) | (z == zMax)):
                            skipBlock = True
                    if ((not skipBlock) & (blockID > 0)):
                        extraValue = extraBuffer[x][y][
                            z]  # TODO (see _readBlocks in mcanvilreader)
                        # AnvilChunkReader.createBlock(
                        #    blockID, (x, y, z), extraValue, meshBuffer)

    wm.progress_end()
    tBuild0 = datetime.datetime.now()

    print("creating clusters")
    bc = BlockCluster(OPTIONS)
    bc.create_cluster((blockBuffer, extraBuffer))
    print("clusters complete")

    if (OPTIONS['showslimes']):
        batchSlimeChunks(slimeBuffer)
    tBuild1 = datetime.datetime.now()
    tBuildTime = tBuild1 - tBuild0
    print("Built meshes in %.2fs" % tBuildTime.total_seconds())

    print("%s: loaded %d chunks" % (worldSelected, totalchunks))
    if len(unknownBlockIDs) > 0:
        print("Unknown new Minecraft datablock IDs encountered:")
        print(" ".join(["%d" % bn for bn in unknownBlockIDs]))

    # Viewport performance hides:
    if (OPTIONS['fasterViewport']):
        hideIfPresent('mcStone')
        hideIfPresent('mcDirt')
        hideIfPresent('mcSandstone')
        hideIfPresent('mcIronOre')
        hideIfPresent('mcGravel')
        hideIfPresent('mcCoalOre')
        hideIfPresent('mcBedrock')
        hideIfPresent('mcRedstoneOre')

    # Profile/run stats:
    chunkReadTotal = tChunkReadTimes[0]
    for tdiff in tChunkReadTimes[1:]:
        chunkReadTotal = chunkReadTotal + tdiff
    print("Total chunk reads time: %.2fs" % chunkReadTotal)
          # I presume that's in seconds, ofc... hm.
    chunkMRT = chunkReadTotal / len(tChunkReadTimes)
    print("Mean chunk read time: %.2fs" % chunkMRT)
    print("Block points processed: %d" % REPORTING['blocksread'])
    print("of those, verts dumped: %d" % REPORTING['blocksdropped'])
    if REPORTING['blocksread'] > 0:
        print("Difference (expected vertex count): %d" %
              (REPORTING['blocksread'] - REPORTING['blocksdropped']))
        print("Hollowing has made the scene %d%% lighter" %
              ((REPORTING['blocksdropped'] / REPORTING['blocksread']) * 100))

    # increase viewport clip dist to see the world! (or decrease mesh sizes)
    # bpy.types.Space...
    # Actually: scale world root down to 0.05 by default?


def blockSurroundedBy(blockAry, blockGroupAry, x, y, z):
    # id = blockAry[x][y][z]
    # if (id in blockGroupAry):
    # print("xyz: "+str(x)+", "+str(y)+", "+str(z))
    bl_u = blockAry[x][y][z + 1]
    if (bl_u in blockGroupAry):
        bl_d = blockAry[x][y][z - 1]
        if (bl_d in blockGroupAry):
            bl_l = blockAry[x - 1][y][z]
            if (bl_l in blockGroupAry):
                bl_r = blockAry[x + 1][y][z]
                if (bl_r in blockGroupAry):
                    bl_f = blockAry[x][y - 1][z]
                    if (bl_f in blockGroupAry):
                        bl_b = blockAry[x][y + 1][z]
                        if (bl_b in blockGroupAry):
                            return True
    return False


def hideIfPresent(mName):
    if mName in bpy.data.objects:
        bpy.data.objects[mName].hide = True


# Feature TODOs
# surface load (skin only, not block instances)
# torch, stairs, rails, redrep meshblocks.
# nether load
# mesh optimisations
# multiple loads per run -- need to name new meshes each time load performed, ie mcGrass.001
# ...
