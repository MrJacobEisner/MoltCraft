PLOT_SIZE = 64
BORDER_WIDTH = 1
BUILDABLE_SIZE = PLOT_SIZE - (BORDER_WIDTH * 2)
GROUND_Y = -60
GAP = 8
BORDER_BLOCK = "minecraft:stone_brick_wall"
BORDER_FLOOR_BLOCK = "minecraft:stone_bricks"


def get_next_grid_coords(taken_plots: set) -> tuple[int, int]:
    for x, z in spiral_generator():
        if (x, z) not in taken_plots:
            return (x, z)


def grid_to_world(grid_x: int, grid_z: int) -> dict:
    x1 = grid_x * (PLOT_SIZE + GAP)
    z1 = grid_z * (PLOT_SIZE + GAP)
    world_x = x1 + PLOT_SIZE // 2
    world_z = z1 + PLOT_SIZE // 2
    return {"x": world_x, "y": GROUND_Y, "z": world_z}


def get_plot_bounds(grid_x: int, grid_z: int) -> dict:
    x1 = grid_x * (PLOT_SIZE + GAP)
    z1 = grid_z * (PLOT_SIZE + GAP)
    x2 = x1 + PLOT_SIZE - 1
    z2 = z1 + PLOT_SIZE - 1
    return {"x1": x1, "z1": z1, "x2": x2, "z2": z2}


def get_buildable_bounds(grid_x: int, grid_z: int) -> dict:
    bounds = get_plot_bounds(grid_x, grid_z)
    return {
        "x1": bounds["x1"] + BORDER_WIDTH,
        "z1": bounds["z1"] + BORDER_WIDTH,
        "x2": bounds["x2"] - BORDER_WIDTH,
        "z2": bounds["z2"] - BORDER_WIDTH,
    }


def get_buildable_origin(grid_x: int, grid_z: int) -> dict:
    b = get_buildable_bounds(grid_x, grid_z)
    center_x = (b["x1"] + b["x2"]) // 2
    center_z = (b["z1"] + b["z2"]) // 2
    return {"x": center_x, "y": GROUND_Y, "z": center_z}


def get_border_commands(grid_x: int, grid_z: int) -> list[str]:
    bounds = get_plot_bounds(grid_x, grid_z)
    x1, z1, x2, z2 = bounds["x1"], bounds["z1"], bounds["x2"], bounds["z2"]
    y = GROUND_Y
    commands = []

    commands.append(f"/fill {x1} {y} {z1} {x2} {y} {z2} {BORDER_FLOOR_BLOCK}")

    bx1 = x1 + BORDER_WIDTH
    bz1 = z1 + BORDER_WIDTH
    bx2 = x2 - BORDER_WIDTH
    bz2 = z2 - BORDER_WIDTH
    commands.append(f"/fill {bx1} {y} {bz1} {bx2} {y} {bz2} minecraft:grass_block")

    commands.append(f"/fill {x1} {y + 1} {z1} {x2} {y + 1} {z1} {BORDER_BLOCK}")
    commands.append(f"/fill {x1} {y + 1} {z2} {x2} {y + 1} {z2} {BORDER_BLOCK}")
    commands.append(f"/fill {x1} {y + 1} {z1} {x1} {y + 1} {z2} {BORDER_BLOCK}")
    commands.append(f"/fill {x2} {y + 1} {z1} {x2} {y + 1} {z2} {BORDER_BLOCK}")

    return commands


def spiral_generator():
    yield (0, 0)

    layer = 1
    while True:
        for z_val in range(-(layer - 1), layer + 1):
            yield (layer, z_val)

        for x_val in range(layer - 1, -layer - 1, -1):
            yield (x_val, layer)

        for z_val in range(layer - 1, -layer - 1, -1):
            yield (-layer, z_val)

        for x_val in range(-layer + 1, layer + 1):
            yield (x_val, -layer)

        layer += 1
