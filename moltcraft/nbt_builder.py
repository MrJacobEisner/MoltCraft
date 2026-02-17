import os
from nbtlib import File, Compound, String, Int, List

STRUCTURE_DIR = os.path.join(os.path.dirname(__file__), "..", "minecraft-server", "world", "generated", "moltcraft", "structures")
DATA_VERSION = 3953


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
        name, properties = _parse_block(block)

        palette_entry = Compound({"Name": String(name)})
        if properties:
            palette_entry["Properties"] = Compound({k: String(v) for k, v in properties.items()})

        palette_map[block] = len(palette_list)
        palette_list.append(palette_entry)

    nbt_blocks = []
    for (x, y, z), block in solid_blocks.items():
        nbt_blocks.append(Compound({
            "pos": List[Int]([Int(x - min_x), Int(y - min_y), Int(z - min_z)]),
            "state": Int(palette_map[block]),
        }))

    structure = File({
        "": Compound({
            "DataVersion": Int(DATA_VERSION),
            "author": String("MoltCraft"),
            "size": List[Int]([Int(size_x), Int(size_y), Int(size_z)]),
            "palette": List[Compound](palette_list),
            "blocks": List[Compound](nbt_blocks),
            "entities": List[Compound]([]),
        })
    })

    os.makedirs(STRUCTURE_DIR, exist_ok=True)

    filename = f"build_{project_id}.nbt"
    filepath = os.path.join(STRUCTURE_DIR, filename)
    structure.save(filepath, gzipped=True)

    return f"moltcraft:build_{project_id}"


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


def get_structure_offset(blocks: dict, origin: dict) -> tuple:
    solid_blocks = {pos: block for pos, block in blocks.items()
                    if block not in ("minecraft:air", "air")}

    if not solid_blocks:
        return (origin["x"], origin["y"], origin["z"])

    min_x = min(pos[0] for pos in solid_blocks)
    min_y = min(pos[1] for pos in solid_blocks)
    min_z = min(pos[2] for pos in solid_blocks)

    return (
        origin["x"] + min_x,
        origin["y"] + min_y,
        origin["z"] + min_z,
    )
