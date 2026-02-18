import os
import glob
import gzip
import struct
import io
import time

STRUCTURE_DIR = os.path.join(os.path.dirname(__file__), "..", "minecraft-server", "world", "generated", "moltcraft", "structures")
DATA_VERSION = 3953


class _NBTWriter:
    def __init__(self):
        self.buf = io.BytesIO()

    def _byte(self, v):
        self.buf.write(struct.pack('>b', v))

    def _short(self, v):
        self.buf.write(struct.pack('>h', v))

    def _int(self, v):
        self.buf.write(struct.pack('>i', v))

    def _string(self, s):
        encoded = s.encode('utf-8')
        self._short(len(encoded))
        self.buf.write(encoded)

    def tag_int(self, name, value):
        self._byte(3)
        self._string(name)
        self._int(value)

    def tag_string(self, name, value):
        self._byte(8)
        self._string(name)
        self._string(value)

    def tag_list_int(self, name, values):
        self._byte(9)
        self._string(name)
        self._byte(3)
        self._int(len(values))
        for v in values:
            self._int(v)

    def begin_compound(self, name=""):
        self._byte(10)
        self._string(name)

    def end_compound(self):
        self._byte(0)

    def begin_list_compound(self, name, length):
        self._byte(9)
        self._string(name)
        self._byte(10)
        self._int(length)

    def getvalue(self):
        return self.buf.getvalue()


def _parse_block(block: str) -> tuple:
    if ":" not in block.split("[")[0]:
        block = "minecraft:" + block

    if "[" in block:
        name = block[:block.index("[")]
        props_str = block[block.index("[") + 1:block.rindex("]")]
        properties = {}
        for prop in props_str.split(","):
            key, value = prop.strip().split("=", 1)
            properties[key.strip()] = value.strip()
        return name, properties
    else:
        return block, {}


def blocks_to_nbt(blocks: dict, project_id: int) -> str:
    solid_blocks = {pos: block for pos, block in blocks.items()
                    if block not in ("minecraft:air", "air")}

    if not solid_blocks:
        return None

    min_x = min(pos[0] for pos in solid_blocks)
    min_y = min(pos[1] for pos in solid_blocks)
    min_z = min(pos[2] for pos in solid_blocks)
    max_x = max(pos[0] for pos in solid_blocks)
    max_y = max(pos[1] for pos in solid_blocks)
    max_z = max(pos[2] for pos in solid_blocks)

    size_x = max_x - min_x + 1
    size_y = max_y - min_y + 1
    size_z = max_z - min_z + 1

    palette_map = {}
    palette_list = []
    for block in sorted(set(solid_blocks.values())):
        palette_map[block] = len(palette_list)
        palette_list.append(block)

    w = _NBTWriter()
    w._byte(10)
    w._short(0)

    w.tag_int("DataVersion", DATA_VERSION)
    w.tag_list_int("size", [size_x, size_y, size_z])

    w.begin_list_compound("palette", len(palette_list))
    for block in palette_list:
        name, properties = _parse_block(block)
        w.tag_string("Name", name)
        if properties:
            w.begin_compound("Properties")
            for k, v in sorted(properties.items()):
                w.tag_string(k, v)
            w.end_compound()
        w.end_compound()

    w.begin_list_compound("blocks", len(solid_blocks))
    for (x, y, z), block in solid_blocks.items():
        w.tag_list_int("pos", [x - min_x, y - min_y, z - min_z])
        w.tag_int("state", palette_map[block])
        w.end_compound()

    w.begin_list_compound("entities", 0)

    w.end_compound()

    os.makedirs(STRUCTURE_DIR, exist_ok=True)

    for old_file in glob.glob(os.path.join(STRUCTURE_DIR, f"build_{project_id}_*.nbt")):
        try:
            os.remove(old_file)
        except OSError:
            pass
    legacy = os.path.join(STRUCTURE_DIR, f"build_{project_id}.nbt")
    if os.path.exists(legacy):
        try:
            os.remove(legacy)
        except OSError:
            pass

    ts = int(time.time() * 1000)
    stem = f"build_{project_id}_{ts}"
    filepath = os.path.join(STRUCTURE_DIR, f"{stem}.nbt")
    with open(filepath, 'wb') as f:
        f.write(gzip.compress(w.getvalue()))

    return f"moltcraft:{stem}"


RESET_HEIGHT = 124

def generate_reset_nbt() -> str:
    os.makedirs(STRUCTURE_DIR, exist_ok=True)
    filepath = os.path.join(STRUCTURE_DIR, "plot_reset.nbt")
    if os.path.exists(filepath):
        return "moltcraft:plot_reset"

    from grid import PLOT_SIZE

    size_x = PLOT_SIZE
    size_z = PLOT_SIZE
    size_y = RESET_HEIGHT

    palette_list = [
        "minecraft:grass_block",
        "minecraft:air",
    ]

    blocks_list = []
    for x in range(size_x):
        for z in range(size_z):
            blocks_list.append(((x, 0, z), 0))
            for y in range(1, size_y):
                blocks_list.append(((x, y, z), 1))

    w = _NBTWriter()
    w._byte(10)
    w._short(0)

    w.tag_int("DataVersion", DATA_VERSION)
    w.tag_list_int("size", [size_x, size_y, size_z])

    w.begin_list_compound("palette", len(palette_list))
    for block in palette_list:
        w.tag_string("Name", block)
        w.end_compound()

    w.begin_list_compound("blocks", len(blocks_list))
    for (x, y, z), state in blocks_list:
        w.tag_list_int("pos", [x, y, z])
        w.tag_int("state", state)
        w.end_compound()

    w.begin_list_compound("entities", 0)
    w.end_compound()

    with open(filepath, 'wb') as f:
        f.write(gzip.compress(w.getvalue()))

    print(f"[NBT] Generated plot reset template ({size_x}x{size_y}x{size_z}, {len(blocks_list)} blocks)")
    return "moltcraft:plot_reset"


def get_structure_offset(blocks: dict, origin: dict) -> tuple:
    solid_blocks = {pos: block for pos, block in blocks.items()
                    if block not in ("minecraft:air", "air")}

    if not solid_blocks:
        return (origin["x"], origin["y"], origin["z"])

    min_x = min(pos[0] for pos in solid_blocks)
    min_y = min(pos[1] for pos in solid_blocks)
    min_z = min(pos[2] for pos in solid_blocks)

    world_y = origin["y"] + min_y
    if world_y < -64:
        world_y = -64

    return (
        origin["x"] + min_x,
        world_y,
        origin["z"] + min_z,
    )
