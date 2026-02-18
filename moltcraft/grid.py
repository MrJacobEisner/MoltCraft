PLOT_SIZE = 64
GROUND_Y = -60
GAP = 8
STRIDE = PLOT_SIZE + GAP
HALF = PLOT_SIZE // 2


def get_next_grid_coords(taken_plots: set) -> tuple[int, int]:
    for x, z in spiral_generator():
        if (x, z) not in taken_plots:
            return (x, z)


def grid_to_world(grid_x: int, grid_z: int) -> dict:
    x1 = grid_x * STRIDE - HALF
    z1 = grid_z * STRIDE - HALF
    world_x = x1 + HALF
    world_z = z1 + HALF
    return {"x": world_x, "y": GROUND_Y, "z": world_z}


def get_plot_bounds(grid_x: int, grid_z: int) -> dict:
    x1 = grid_x * STRIDE - HALF
    z1 = grid_z * STRIDE - HALF
    x2 = x1 + PLOT_SIZE - 1
    z2 = z1 + PLOT_SIZE - 1
    return {"x1": x1, "z1": z1, "x2": x2, "z2": z2}


def get_buildable_origin(grid_x: int, grid_z: int) -> dict:
    b = get_plot_bounds(grid_x, grid_z)
    center_x = (b["x1"] + b["x2"] + 1) // 2
    center_z = (b["z1"] + b["z2"] + 1) // 2
    return {"x": center_x, "y": GROUND_Y, "z": center_z}


def get_decoration_commands(grid_x: int, grid_z: int) -> list[str]:
    bounds = get_plot_bounds(grid_x, grid_z)
    x1, z1, x2, z2 = bounds["x1"], bounds["z1"], bounds["x2"], bounds["z2"]
    y = GROUND_Y
    commands = []

    ox1, oz1 = x1 - GAP, z1 - GAP
    ox2, oz2 = x2 + GAP, z2 + GAP

    commands.append(f"/fill {ox1} {y} {oz1} {ox2} {y} {oz2} minecraft:stone_bricks")

    commands.append(f"/fill {x1} {y} {z1} {x2} {y} {z2} minecraft:grass_block")

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
