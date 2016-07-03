import os
import bpy

from struct import unpack  # , error as StructError
from . import nbtreader, mcregionreader
from .mineregion import OPTIONS, EXCLUDED_BLOCKS,  REPORTING, unknownBlockIDs, WORLD_ROOT
# ..yuck: they're immutable and don't return properly except for the dict-type ones. Get rid of this in next cleanup.

from math import floor
from .blocks.block import Block


class AnvilChunkReader(mcregionreader.ChunkReader):

    # readBlock( bX, bZ (by?) ...  ignoring 'region' boundaries and chunk
    # boundaries? We need an ignore-chunk-boundaries level of abstraction

    def getSingleBlock(chunkXZ, blockXYZ):  # returns the value and extradata bits for a single block of given absolute x,y,z block coords within chunk cx,cz. or None if area not generated.
        # y is value from 0..255
        cx, cy = chunkXZ
        bX, bY, bZ = blockXYZ
        rX = floor(cx / 32)  # is this the same as >> 8 ??
        rZ = floor(cz / 32)
        rHdrOffset = ((cx % 32) + (cz % 32) * 32) * 4
        rFile = "r.%d.%d.mca" % (rx, rz)
        if not os.path.exists(rFile):
            return None
        with open(rFile, 'rb') as regionfile:
            regionfile.seek(rheaderoffset)
            cheadr = regionfile.read(4)
            dataoffset = unpack(">i", b'\x00' + cheadr[0:3])[0]
            chunksectorcount = cheadr[3]
            if dataoffset == 0 and chunksectorcount == 0:
                return None  # Region exists, but the chunk we're after was never created within it.
            else:
                # possibly check for cached chunk data here, under the cx,cz in
                # a list of already-loaded sets.
                chunkdata = AnvilChunkReader._readChunkData(
                    regionfile, dataoffset, chunksectorcount)
                chunkLvl = chunkdata.value['Level'].value
                sections = chunkLvl['Sections'].value
                # each section is a 16x16x16 piece of chunk, with a Y-byte from 0-15, so that the 'y' value is 16*that + in-section-Y-value
                # some sections can be skipped, so we must iterate to find the
                # right one with the 'Y' we expect.
                bSection = bY / 16
                sect = None
                for section in sections:
                    secY = section.value['Y'].value
                    if secY == bSection:
                        sect = section.value
                if sect is None:
                    return None
                blockData = sec[
                    'Blocks'].value  # a TAG_Byte_Array value (bytes object). Blocks is 16x16 bytes
                extraData = sec[
                    'Data'].value  # BlockLight, Data and SkyLight are 16x16 "4-bit cell" additional data arrays.
                sY = dY % 16
                blockIndex = (sY * 16 + dZ) * 16 + dX
                blockID = blockData[blockIndex]
                return blockID  # , extravalue)
                # NB: this can be made massively more efficient by storing 4 'neighbour chunk' data reads for every chunk properly processed.
                # Don't need to do diagonals, even.

    # def readChunk(self, chunkPosX, chunkPosZ, vertexBuffer, processFunc):  #
    # aka "readChunkFromRegion" ...
    def readChunk(self, chunkPosX, chunkPosZ, processFunc):  # aka "readChunkFromRegion" ...
        """Loads chunk located at the X,Z chunk location provided."""

        global REPORTING

        # region containing a given chunk is found thusly: floor of c over 32
        regionX = floor(chunkPosX / 32)
        regionZ = floor(chunkPosZ / 32)

        rheaderoffset = ((chunkPosX % 32) + (chunkPosZ % 32) * 32) * 4

        # print("Reading chunk %d,%d from region %d,%d" %(chunkPosX, chunkPosZ,
        # regionX,regionZ))

        rfileName = "r.%d.%d.mca" % (regionX, regionZ)
        if not os.path.exists(rfileName):
            # Can't load: it doesn't exist!
            print("No such region generated.")
            return

        with open(rfileName, 'rb') as regfile:
            # header for the chunk we want is at...
            # The location in the region file of a chunk at (x, z) (in chunk coordinates) can be found at byte offset 4 * ((x mod 32) + (z mod 32) * 32) in its McRegion file.
            # Its timestamp can be found 4096 bytes later in the file
            regfile.seek(rheaderoffset)
            cheadr = regfile.read(4)
            dataoffset = unpack(">i", b'\x00' + cheadr[0:3])[0]
            chunksectorcount = cheadr[3]

            if dataoffset == 0 and chunksectorcount == 0:
                pass
                # print("Region exists, but chunk has never been created within
                # it.")
            else:
                chunkdata = AnvilChunkReader._readChunkData(
                    regfile, dataoffset, chunksectorcount)  # todo: rename that function!
                # Geometry creation! etc... If surface only, can get heights etc
                # from lightarray?

                # top level tag in NBT is an unnamed TAG_Compound, for some
                # reason, containing a named TAG_Compound "Level"
                chunkLvl = chunkdata.value['Level'].value
                # chunkXPos = chunkLvl['xPos'].value
                # chunkZPos = chunkLvl['zPos'].value
                # print("Reading blocks for chunk: (%d, %d)\n" % (chunkXPos, chunkZPos))
                # AnvilChunkReader._readBlocks(chunkLvl, vertexBuffer)
                processFunc(chunkLvl)
                # print("Loaded chunk %d,%d" % (chunkPosX,chunkPosZ))

                REPORTING['totalchunks'] += 1

    def processChunk2(self, chunkPosX, chunkPosZ, blockBuffer, extraBuffer, zeroAdjX, zeroAdjZ):
        # FIXME - implement me!
        # print("reading chunk: "+str(chunkPosX)+","+str(chunkPosZ)+" offset:
        # "+str(zeroAdjX)+", "+str(zeroAdjZ)+" array chunk index:
        # "+str(chunkPosX+zeroAdjX)+", "+str(chunkPosZ+zeroAdjZ))
        def _internalProcessChunk2(lvl):  # handle chunk
            def _internalProcessBlock2(block, extra, dX, dY, dZ):  # handle blocks within a chunk
                baseX = (chunkPosX + zeroAdjX) * 16
                # baseY = (chunkPosY+zeroAdjY)*16
                baseZ = (chunkPosZ + zeroAdjZ) * 16
                blockBuffer[baseX + dX][dY][baseZ + dZ] = block
                extraBuffer[baseX + dX][dY][baseZ + dZ] = extra
                # pass
            # pass
            AnvilChunkReader._processBlocks(lvl, _internalProcessBlock2)

        self.readChunk(chunkPosX, chunkPosZ, _internalProcessChunk2)

    def processChunk(self, chunkPosX, chunkPosY, vertexBuffer):
        def _internalProcessChunk(lvl):
            AnvilChunkReader._readBlocks(
                lvl, vertexBuffer)  # once _processBlocks above is done, migrate to this and eliminate _readBlocks

        self.readChunk(chunkPosX, chunkPosY, _internalProcessChunk)

    def _readChunkData(bstream, chunkOffset, chunkSectorCount):  # rename this!
        # get the datastring out of the file...
        import io
        import zlib

        # cf = open(fname, 'rb')
        initialPos = bstream.tell()

        cstart = chunkOffset * 4096  # 4 kiB
        clen = chunkSectorCount * 4096
        bstream.seek(cstart)  # this bstream is the region file

        chunkHeaderAndData = bstream.read(clen)

        # chunk header stuff is:
        # 4 bytes: length (of remaining data)
        # 1 byte : compression type (1 - gzip - unused; 2 - zlib: it should always be this in actual fact)
        # then the rest, is length-1 bytes of compressed (zlib) NBT data.

        chunkDLength = unpack(">i", chunkHeaderAndData[0:4])[0]
        chunkDCompression = chunkHeaderAndData[4]
        if chunkDCompression != 2:
            print("Not a zlib-compressed chunk!?")
            raise StringError()  # MinecraftSomethingError, perhaps.

        chunkZippedBytes = chunkHeaderAndData[5:]

        # could/should check that chunkZippedBytes is same length as
        # chunkDLength-1.

        # put the regionfile byte stream back to where it started:
        bstream.seek(initialPos)

        # Read the compressed chunk data
        zipper = zlib.decompressobj()
        chunkData = zipper.decompress(chunkZippedBytes)
        chunkDataAsFile = io.BytesIO(chunkData)
        chunkNBT = nbtreader.readNBT(chunkDataAsFile)

        return chunkNBT

    def getSectionBlock(blockLoc, sectionDict):
        """Fetches a block from section NBT data."""
        (bX, bY, bZ) = blockLoc
        secY = bY >> 4  # / 16
        if secY not in sectionDict:
            return None
        sect = sectionDict[secY]
        sY = bY & 0xf  # mod 16
        bIndex = (sY * 16 + bZ) * 16 + bX
        # bitshift, or run risk of int casts
        dat = sect['Blocks'].value
        return dat[bIndex]

    # Hollow volumes optimisation (version1: in-chunk only)
    def _isExposedBlock(blockCoord, chunkXZ, secBlockData, sectionDict, blockID, skyHighLimit, depthLimit):  # another param: neighbourChunkData[] - a 4-list of NBT stuff...
        (dX, dY, dZ) = blockCoord
        # fail-fast. checks if all ortho adjacent neighbours fall inside this chunk.
        # EASY! Because it's 0-15 for both X and Z. For Y, we're iterating upward,
        # so get the previous value (the block below) passed in.

        if blockID == 18:  # leaves   #and glass? and other exemptions?
            return True

        if dX == 0 or dX == 15 or dY == 0 or dZ == 0 or dZ == 15:
            # get neighbour directly
            return True  # instead, check neigbouring chunks...

        # we can no longer get the block below or above easily as we might be
        # iterating +x, -16x, or +z at any given step.
        if dY == skyHighLimit or dY == depthLimit:
            return True

        ySect = dY / \
            16  # all this dividing integers by 16! I ask you! (>> 4)!
        yBoff = dY % 16  # &= 0x0f
        # if you are on a section boundary, need next section for block above.
        # else

        # GLOBALS (see readBlocks, below)
        CHUNKSIZE_X = 16  # static consts - global?
        CHUNKSIZE_Z = 16
        # new layout goes YZX. improves compression, apparently.
        # _Y_SHIFT = 7    # 2**7 is 128. use for fast multiply
        # _YZ_SHIFT = 11    #16 * 128 is 2048, which is 2**11

        # check above (Y+1)
        # either it's in the same section (quick/easy lookup) or it's in another section (still quite easy - next array over)
        # or, it's in another chunk. in which case, check chunkreadcache for the 4 adjacent. Failing this, it's the worse case and
        # we need to read into a whole new chunk data grab.
        if yBoff == 15:
            upBlock = AnvilChunkReader.getSectionBlock(
                (dX, dY + 1, dZ), sectionDict)
            if upBlock != blockID:
                return True
        else:
            # get it from current section
            upIndex = ((yBoff + 1) * 16 + dZ) * 16 + dX
            upBlock = secBlockData[upIndex]
            if upBlock != blockID:
                return True

        # Check below (Y-1):
        if yBoff == 0:
            downBlock = AnvilChunkReader.getSectionBlock(
                (dX, dY - 1, dZ), sectionDict)
            if downBlock != blockID:
                return True
        else:
            downIndex = ((yBoff - 1) * 16 + dZ) * 16 + dX
            dnBlock = secBlockData[downIndex]
            if dnBlock != blockID:
                return True

        # Have checked above and below; now check all sides. Same section, but maybe different chunks...
        # Check X-1 (leftward)
        leftIndex = (yBoff * 16 + dZ) * 16 + (dX - 1)
        # ngbIndex = dY + (dZ << _Y_SHIFT) + ((dX-1) << _YZ_SHIFT)    #Check
        # this lookup in readBlocks, below! Can it go o.o.b.?
        try:
            neighbour = secBlockData[leftIndex]
        except IndexError:
            print("Bogus index cockup: %d. Blockdata len is 16x16x16 bytes (4096)." %
                  leftIndex)
            quit()
        if neighbour != blockID:
            return True

        # Check X+1
        rightIndex = (yBoff * 16 + dZ) * 16 + (dX + 1)
        # ngbIndex = dY + (dZ << _Y_SHIFT) + ((dX+1) << _YZ_SHIFT)    #Check
        # this lookup in readBlocks, below! Can it go o.o.b.?
        neighbour = secBlockData[rightIndex]
        if neighbour != blockID:
            return True

        # Check Z-1
        ngbIndex = (yBoff * 16 + (dZ - 1)) * 16 + dX
        # ngbIndex = dY + ((dZ-1) << _Y_SHIFT) + (dX << _YZ_SHIFT)    #Check
        # this lookup in readBlocks, below! Can it go o.o.b.?
        neighbour = secBlockData[ngbIndex]
        if neighbour != blockID:
            return True

        # Check Z+1
        ngbIndex = (yBoff * 16 + (dZ + 1)) * 16 + dX
        # ngbIndex = dY + ((dZ+1) << _Y_SHIFT) + (dX << _YZ_SHIFT)    #Check
        # this lookup in readBlocks, below! Can it go o.o.b.?
        neighbour = secBlockData[ngbIndex]
        if neighbour != blockID:
            return True

        return False

    def _processBlocks(chunkLevelData, processFunc):
        """readBlocks(chunkLevelData) -> takes a named TAG_Compound 'Level' containing a chunk's Anvil Y-Sections, each of which 0-15 has blocks, data, heightmap, xpos,zpos, etc.
    Adds the data points into a 'vertexBuffer' which is a per-named-type dictionary of ????'s. That later is made into Blender geometry via from_pydata."""
        # TODO: also TileEntities and Entities. Entities will generally be an empty list.
        # TileEntities are needed for some things to define fully...

        # TODO: Keep an 'adjacent chunk cache' for neighbourhood is-exposed
        # checks.

        global unknownBlockIDs, OPTIONS, REPORTING

        # chunkLocation = 'xPos' 'zPos' ...
        chunkX = chunkLevelData['xPos'].value
        chunkZ = chunkLevelData['zPos'].value
        biomes = chunkLevelData[
            'Biomes'].value  # yields a TAG_Byte_Array value (bytes object) of len 256 (16x16)
        # heightmap = chunkLevelData['HeightMap'].value
        #'TileEntities' -- surely need this for piston data and stuff, no?

        entities = chunkLevelData[
            'Entities'].value    # load ze sheeps!! # a list of tag-compounds.
        # omitmobs = OPTIONS['omitmobs']
        if not OPTIONS['omitmobs']:
            AnvilChunkReader._loadEntities(entities)

        skyHighLimit = OPTIONS['highlimit']
        depthLimit = OPTIONS['lowlimit']

        CHUNKSIZE_X = 16
        CHUNKSIZE_Z = 16
        SECTNSIZE_Y = 16

        # _Y_SHIFT = 7    # 2**7 is 128. use for fast multiply
        # _YZ_SHIFT = 11    #16 * 128 is 2048, which is 2**11
        sections = chunkLevelData['Sections'].value

        # each section is a 16x16x16 piece of chunk, with a Y-byte from 0-15, so
        # that the 'y' value is 16*that + in-section-Y-value

        # iterate through all block Y values from bedrock to max height (minor step through X,Z.)
        # bearing in mind some can be skipped out.

        # sectionDict => a dictionary of sections, indexed by Y.
        sDict = {}
        for section in sections:
            sY = section.value['Y'].value
            sDict[sY] = section.value

        for section in sections:
            sec = section.value
            secY = sec['Y'].value * SECTNSIZE_Y

            # if (secY + 16) < lowlimit, skip this section. no need to load it.
            if (secY + 16 < depthLimit):
                continue

            if (secY > skyHighLimit):
                return

            # Now actually proceed with adding in the section's block data.
            blockData = sec[
                'Blocks'].value  # yields a TAG_Byte_Array value (bytes object). Blocks is 16x16 bytes
            extraData = sec[
                'Data'].value  # BlockLight, Data and SkyLight are 16x16 "4-bit cell" additional data arrays.
            add = sec["Add"].value if "Add" in sec.keys() else None
            # get starting Y from heightmap, ignoring excess height iterations...
            # heightByte = heightMap[dX + (dZ << 4)]    # z * 16
            # heightByte = 255    #quickFix: start from tip top, for now
            # if heightByte > skyHighLimit:
            #    heightByte = skyHighLimit

            # go y 0 to 16...
            for sy in range(16):
                dY = secY + sy

                if dY < depthLimit:
                    continue
                if dY > skyHighLimit:
                    return

                # dataX will be dX, blender X will be bX.
                for dZ in range(CHUNKSIZE_Z):
                    for dX in range(CHUNKSIZE_X):
                        blockIndex = sy * 16 * 16 + dZ * 16 + dX
                        blockID = blockData[blockIndex]

                        # create this block in the output!

                        if blockID != 0 and blockID not in EXCLUDED_BLOCKS:    # 0 is air
                            REPORTING['blocksread'] += 1
                            if any(d["type"] == blockID for d in Block.defs):
                                extraValue = AnvilChunkReader.nibble4(
                                    blockData, blockIndex)
                                processFunc(blockID, extraValue, dX, dY, dZ)
                            else:
                                unknownBlockIDs.add(blockID)

    def nibble4(arr, idx):
        return arr[int(idx / 2)] & 0x0f if idx % 2 == 0 else (arr[int(idx / 2)] >> 4) & 0x0f

    def _loadEntities(entities):
        global WORLD_ROOT
        for e in entities:
            eData = e.value

            etypename = eData['id'].value  # eg 'Sheep'
            ename = "en%sMarker" % etypename
            epos = [p.value for p in eData['Pos'].value]  # list[3] of double
            erot = [r.value for r in eData['Rotation'].value]
                # list[2] of float ([0] orientation (angle round Z-axis) and [1]
                # 0.00, probably y-tilt.

            # instantiate and rotate-in a placeholder object for this (and add to controlgroup or parent to something handy.)
            # translate to blend coords, too.
            entMarker = bpy.data.objects.new(ename, None)
            # set its coordinates...
            # convert Minecraft coordinate position of player into Blender
            # coords:
            entMarker.location[0] = -epos[2]
            entMarker.location[1] = -epos[0]
            entMarker.location[2] = epos[1]

            # also, set its z-rotation to erot[0]...
            # entMarker.rotation[2] = erot[0]

            bpy.context.scene.objects.link(entMarker)
            entMarker.parent = WORLD_ROOT
