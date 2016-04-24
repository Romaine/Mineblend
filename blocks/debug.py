""" This handles relative imports"""

from importlib import reload
from Mineblend.blocks import block, resourcepacks

reload(block)
reload(resourcepacks)

resourcepacks.main()
block.main()
