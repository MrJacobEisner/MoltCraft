import math

MAX_RADIUS = 50
MAX_DIMENSION = 200


class MinecraftBuilder:

    class BuildBoundsError(Exception):
        pass

    def __init__(self):
        self.blocks = {}

    def _add_block(self, x, y, z, block):
        block_name = str(block)
        if not block_name.startswith("minecraft:"):
            block_name = f"minecraft:{block_name}"
        self.blocks[(int(x), int(y), int(z))] = block_name

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
        x1, y1, z1 = int(x1), int(y1), int(z1)
        x2, y2, z2 = int(x2), int(y2), int(z2)
        mn_x, mx_x = min(x1, x2), max(x1, x2)
        mn_y, mx_y = min(y1, y2), max(y1, y2)
        mn_z, mx_z = min(z1, z2), max(z1, z2)
        for x in range(mn_x, mx_x + 1):
            for y in range(mn_y, mx_y + 1):
                for z in range(mn_z, mx_z + 1):
                    pos = (x, y, z)
                    if replace_block is None or self.blocks.get(pos, "").endswith(replace_block):
                        self._add_block(x, y, z, block)

    def wall(self, x1, y1, z1, x2, y2, z2, block):
        self.fill(x1, y1, z1, x2, y2, z2, block)

    def floor(self, x1, y1, z1, x2, z2, block):
        self.fill(x1, y1, z1, x2, y1, z2, block)

    def box(self, x, y, z, width, height, depth, block, hollow=True):
        width = int(width)
        height = int(height)
        depth = int(depth)
        self._check_dimension(max(width, height, depth), "Box dimension")
        x2 = x + width - 1
        y2 = y + height - 1
        z2 = z + depth - 1
        if hollow:
            self.fill_hollow(x, y, z, x2, y2, z2, block)
        else:
            self.fill(x, y, z, x2, y2, z2, block)

    def cylinder(self, cx, cy, cz, radius, height, block, hollow=True, axis="y"):
        radius = int(radius)
        height = int(height)
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
        radius = int(radius)
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
        radius = int(radius)
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
        x1, y1, z1 = int(x1), int(y1), int(z1)
        x2, y2, z2 = int(x2), int(y2), int(z2)
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
        radius = int(radius)
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
        radius = int(radius)
        start_angle = int(start_angle)
        end_angle = int(end_angle)
        self._check_radius(radius)
        for angle in range(start_angle, end_angle + 1):
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

    def spiral(self, cx, cy, cz, radius, height, block, turns=1):
        radius = int(radius)
        height = int(height)
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
        base_size = int(base_size)
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
        length = int(length)
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
        return len(self.blocks)

    def generate_commands(self, offset=(0, 0, 0)):
        if not self.blocks:
            return []

        ox, oy, oz = offset

        by_type = {}
        for pos, block in self.blocks.items():
            if block not in by_type:
                by_type[block] = set()
            by_type[block].add(pos)

        commands = []
        for block, positions in by_type.items():
            regions = _optimize_fill_regions(positions)
            for (x1, y1, z1, x2, y2, z2) in regions:
                x1, y1, z1 = x1 + ox, y1 + oy, z1 + oz
                x2, y2, z2 = x2 + ox, y2 + oy, z2 + oz
                if x1 == x2 and y1 == y2 and z1 == z2:
                    commands.append(f"setblock {x1} {y1} {z1} {block} replace")
                else:
                    commands.append(f"fill {x1} {y1} {z1} {x2} {y2} {z2} {block} replace")

        return commands


def _optimize_fill_regions(positions):
    if not positions:
        return []

    remaining = set(positions)
    regions = []

    sorted_positions = sorted(remaining, key=lambda p: (p[1], p[2], p[0]))

    for pos in sorted_positions:
        if pos not in remaining:
            continue

        x, y, z = pos

        max_x = x
        while (max_x + 1, y, z) in remaining:
            max_x += 1

        max_z = z
        z_expandable = True
        while z_expandable:
            for xi in range(x, max_x + 1):
                if (xi, y, max_z + 1) not in remaining:
                    z_expandable = False
                    break
            if z_expandable:
                max_z += 1

        max_y = y
        y_expandable = True
        while y_expandable:
            for zi in range(z, max_z + 1):
                for xi in range(x, max_x + 1):
                    if (xi, max_y + 1, zi) not in remaining:
                        y_expandable = False
                        break
                if not y_expandable:
                    break
            if y_expandable:
                max_y += 1

        for xi in range(x, max_x + 1):
            for yi in range(y, max_y + 1):
                for zi in range(z, max_z + 1):
                    remaining.discard((xi, yi, zi))

        regions.append((x, y, z, max_x, max_y, max_z))

    return regions
