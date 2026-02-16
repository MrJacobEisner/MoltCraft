PLOT_SIZE = 64
GROUND_Y = -60
GAP = 8


def get_next_grid_coords(taken_plots: set) -> tuple[int, int]:
    for x, z in spiral_generator():
        if (x, z) not in taken_plots:
            return (x, z)


def grid_to_world(grid_x: int, grid_z: int) -> dict:
    world_x = grid_x * (PLOT_SIZE + GAP) + PLOT_SIZE // 2
    world_z = grid_z * (PLOT_SIZE + GAP) + PLOT_SIZE // 2
    return {"x": world_x, "y": GROUND_Y, "z": world_z}


def get_plot_bounds(grid_x: int, grid_z: int) -> dict:
    x1 = grid_x * (PLOT_SIZE + GAP)
    z1 = grid_z * (PLOT_SIZE + GAP)
    x2 = x1 + PLOT_SIZE - 1
    z2 = z1 + PLOT_SIZE - 1
    return {"x1": x1, "z1": z1, "x2": x2, "z2": z2}


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
