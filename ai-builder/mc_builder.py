import math
from nbt_structure_utils import NBTStructure, Vector, BlockData, Cuboid

MAX_RADIUS = 50
MAX_DIMENSION = 200
MAX_BLOCKS = 500000


class MinecraftBuilder:

    class BuildLimitError(Exception):
        pass

    class BuildBoundsError(Exception):
        pass

    def __init__(self):
        self.structure = NBTStructure()
        self.block_count = 0

    def _add_block(self, x, y, z, block):
        if self.block_count >= MAX_BLOCKS:
            raise MinecraftBuilder.BuildLimitError(
                f"Exceeded maximum of {MAX_BLOCKS} blocks. Simplify your build."
            )
        block_name = str(block)
        if not block_name.startswith("minecraft:"):
            block_name = f"minecraft:{block_name}"

        state = {}
        if "[" in block_name and block_name.endswith("]"):
            base, state_str = block_name.rstrip("]").split("[", 1)
            block_name = base
            for pair in state_str.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    state[k.strip()] = v.strip()

        bd = BlockData(block_name, state) if state else BlockData(block_name)
        self.structure.set_block(Vector(int(x), int(y), int(z)), bd)
        self.block_count += 1

    def _check_radius(self, radius):
        if abs(radius) > MAX_RADIUS:
            raise MinecraftBuilder.BuildBoundsError(
                f"Radius {radius} exceeds max of {MAX_RADIUS}"
            )

    def _check_dimension(self, val, name="Dimension"):
        if abs(val) > MAX_DIMENSION:
            raise MinecraftBuilder.BuildBoundsError(
                f"{name} {val} exceeds max of {MAX_DIMENSION}"
            )

    def place_block(self, x, y, z, block):
        self._add_block(x, y, z, block)

    def fill(self, x1, y1, z1, x2, y2, z2, block, mode="replace"):
        x1, y1, z1 = int(x1), int(y1), int(z1)
        x2, y2, z2 = int(x2), int(y2), int(z2)
        mn_x, mx_x = min(x1, x2), max(x1, x2)
        mn_y, mx_y = min(y1, y2), max(y1, y2)
        mn_z, mx_z = min(z1, z2), max(z1, z2)

        if mode == "hollow":
            for x in range(mn_x, mx_x + 1):
                for y in range(mn_y, mx_y + 1):
                    for z in range(mn_z, mx_z + 1):
                        is_edge = (x == mn_x or x == mx_x or
                                   y == mn_y or y == mx_y or
                                   z == mn_z or z == mx_z)
                        if is_edge:
                            self._add_block(x, y, z, block)
                        else:
                            self._add_block(x, y, z, "air")
        elif mode == "outline":
            for x in range(mn_x, mx_x + 1):
                for y in range(mn_y, mx_y + 1):
                    for z in range(mn_z, mx_z + 1):
                        is_edge = (x == mn_x or x == mx_x or
                                   y == mn_y or y == mx_y or
                                   z == mn_z or z == mx_z)
                        if is_edge:
                            self._add_block(x, y, z, block)
        else:
            for x in range(mn_x, mx_x + 1):
                for y in range(mn_y, mx_y + 1):
                    for z in range(mn_z, mx_z + 1):
                        self._add_block(x, y, z, block)

    def fill_hollow(self, x1, y1, z1, x2, y2, z2, block):
        self.fill(x1, y1, z1, x2, y2, z2, block, "hollow")

    def fill_outline(self, x1, y1, z1, x2, y2, z2, block):
        self.fill(x1, y1, z1, x2, y2, z2, block, "outline")

    def fill_replace(self, x1, y1, z1, x2, y2, z2, block, replace_block=None):
        self.fill(x1, y1, z1, x2, y2, z2, block)

    def wall(self, x1, y1, z1, x2, y2, z2, block):
        self.fill(x1, y1, z1, x2, y2, z2, block)

    def floor(self, x1, y1, z1, x2, z2, block):
        self.fill(x1, y1, z1, x2, y1, z2, block)

    def box(self, x, y, z, width, height, depth, block, hollow=True):
        self._check_dimension(max(width, height, depth), "Box dimension")
        x2 = x + width - 1
        y2 = y + height - 1
        z2 = z + depth - 1
        if hollow:
            self.fill_hollow(x, y, z, x2, y2, z2, block)
        else:
            self.fill(x, y, z, x2, y2, z2, block)

    def cylinder(self, cx, cy, cz, radius, height, block, hollow=True, axis="y"):
        self._check_radius(radius)
        self._check_dimension(height, "Height")
        for h in range(height):
            for dx in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    dist = math.sqrt(dx * dx + dz * dz)
                    if hollow:
                        if radius - 1 < dist <= radius:
                            if axis == "y":
                                self._add_block(cx + dx, cy + h, cz + dz, block)
                            elif axis == "x":
                                self._add_block(cx + h, cy + dx, cz + dz, block)
                            else:
                                self._add_block(cx + dx, cy + dz, cz + h, block)
                    else:
                        if dist <= radius:
                            if axis == "y":
                                self._add_block(cx + dx, cy + h, cz + dz, block)
                            elif axis == "x":
                                self._add_block(cx + h, cy + dx, cz + dz, block)
                            else:
                                self._add_block(cx + dx, cy + dz, cz + h, block)

    def sphere(self, cx, cy, cz, radius, block, hollow=True):
        self._check_radius(radius)
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
                    if hollow:
                        if radius - 1 < dist <= radius:
                            self._add_block(cx + dx, cy + dy, cz + dz, block)
                    else:
                        if dist <= radius:
                            self._add_block(cx + dx, cy + dy, cz + dz, block)

    def dome(self, cx, cy, cz, radius, block, hollow=True):
        self._check_radius(radius)
        for dx in range(-radius, radius + 1):
            for dy in range(0, radius + 1):
                for dz in range(-radius, radius + 1):
                    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
                    if hollow:
                        if radius - 1 < dist <= radius:
                            self._add_block(cx + dx, cy + dy, cz + dz, block)
                    else:
                        if dist <= radius:
                            self._add_block(cx + dx, cy + dy, cz + dz, block)

    def line(self, x1, y1, z1, x2, y2, z2, block):
        dx = x2 - x1
        dy = y2 - y1
        dz = z2 - z1
        steps = max(abs(dx), abs(dy), abs(dz), 1)
        if steps > MAX_DIMENSION * 3:
            raise MinecraftBuilder.BuildBoundsError(f"Line too long: {steps} blocks")
        for i in range(steps + 1):
            t = i / steps if steps > 0 else 0
            x = round(x1 + dx * t)
            y = round(y1 + dy * t)
            z = round(z1 + dz * t)
            self._add_block(x, y, z, block)

    def circle(self, cx, cy, cz, radius, block, axis="y"):
        self._check_radius(radius)
        for angle in range(360):
            rad = math.radians(angle)
            if axis == "y":
                x = round(cx + radius * math.cos(rad))
                z = round(cz + radius * math.sin(rad))
                self._add_block(x, cy, z, block)
            elif axis == "x":
                y = round(cy + radius * math.cos(rad))
                z = round(cz + radius * math.sin(rad))
                self._add_block(cx, y, z, block)
            else:
                x = round(cx + radius * math.cos(rad))
                y = round(cy + radius * math.sin(rad))
                self._add_block(x, y, cz, block)

    def arc(self, cx, cy, cz, radius, start_angle, end_angle, block, axis="y"):
        self._check_radius(radius)
        for angle in range(start_angle, end_angle + 1):
            rad = math.radians(angle)
            if axis == "y":
                x = round(cx + radius * math.cos(rad))
                z = round(cz + radius * math.sin(rad))
                self._add_block(x, cy, z, block)

    def spiral(self, cx, cy, cz, radius, height, block, turns=1):
        self._check_radius(radius)
        self._check_dimension(height, "Height")
        steps = height * 16
        for i in range(steps):
            t = i / steps
            angle = t * turns * 2 * math.pi
            x = round(cx + radius * math.cos(angle))
            z = round(cz + radius * math.sin(angle))
            y = round(cy + t * height)
            self._add_block(x, y, z, block)

    def pyramid(self, cx, cy, cz, base_size, block, hollow=True):
        self._check_dimension(base_size, "Pyramid base")
        for layer in range(base_size // 2 + 1):
            half = base_size // 2 - layer
            x1 = cx - half
            z1 = cz - half
            x2 = cx + half
            z2 = cz + half
            y = cy + layer
            if hollow and layer < base_size // 2:
                for x in range(x1, x2 + 1):
                    self._add_block(x, y, z1, block)
                    self._add_block(x, y, z2, block)
                for z in range(z1 + 1, z2):
                    self._add_block(x1, y, z, block)
                    self._add_block(x2, y, z, block)
            else:
                self.fill(x1, y, z1, x2, y, z2, block)

    def stairs(self, x, y, z, length, direction, block):
        self._check_dimension(length, "Stairs length")
        for i in range(length):
            if direction == "north":
                self._add_block(x, y + i, z - i, block)
            elif direction == "south":
                self._add_block(x, y + i, z + i, block)
            elif direction == "east":
                self._add_block(x + i, y + i, z, block)
            elif direction == "west":
                self._add_block(x - i, y + i, z, block)

    def clear_area(self, x1, y1, z1, x2, y2, z2):
        self.fill(x1, y1, z1, x2, y2, z2, "air")

    def get_block_count(self):
        return self.block_count

    def get_nbt(self):
        return self.structure.get_nbt()

    def get_bounds(self):
        if self.block_count == 0:
            return None, None
        min_c = self.structure.get_min_coords()
        max_c = self.structure.get_max_coords()
        return min_c, max_c

    def save(self, filepath):
        nbt_data = self.structure.get_nbt()
        nbt_data.write_file(filename=filepath)
