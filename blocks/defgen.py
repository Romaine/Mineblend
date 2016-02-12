"""Generate blocks.pkl which contains data value information.

This script is intended to be used as a utility to map minecraft blocks
to their data values.
"""

import pickle
from lxml import etree
# convoluted xml namespace documentation can be found at
# http://lxml.de/xpathxslt.html#namespaces-and-prefixes


tree = etree.parse("blocks/DataValues.svg")
root = tree.getroot()
namespace = "http://www.w3.org/2000/svg"
ns = {"ns": namespace}  # saves us some col space

debug = True
blocks = {}

list = root.xpath("//ns:g/ns:a", namespaces=ns)

for tag in list:
    textobj = tag.xpath("ns:text", namespaces=ns)[0]

    name = tag.xpath("ns:title", namespaces=ns)[0].text
    xd = textobj.xpath("ns:tspan", namespaces=ns)[0].text
    _id = int(textobj.text)
    name_ = str(name).replace(" ", "_")

    if _id not in blocks:
        blocks[_id] = {}
    blocks[_id][int(xd) if xd is not None else 0] = [name]

if debug:
    for item in blocks.items():
        print(item)

with open("blocks.pkl", "wb") as f:
    pickle.dump(blocks, f, protocol=pickle.HIGHEST_PROTOCOL)
