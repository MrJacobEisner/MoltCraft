import math

MAX_RADIUS = 50
MAX_FILL_VOLUME = 32768
MAX_DIMENSION = 200


class MinecraftBuilder:

    class CommandLimitError(Exception):
        pass

    class BuildBoundsError(Exception):
        pass

    def __init__(self, max_commands=10000):
        self.commands = []
        self.max_commands = max_commands

    def _add_command(self, cmd):
        if len(self.commands) >= self.max_commands:
            raise MinecraftBuilder.CommandLimitError(
                f"Exceeded maximum of {self.max_commands} commands. Simplify your build."
            )
        self.commands.append(cmd)

    def _check_radius(self, radius):
        if abs(radius) > MAX_RADIUS:
            raise MinecraftBuilder.BuildBoundsError(
                f"Radius {radius} exceeds max of {MAX_RADIUS}"
            )

    def _check_fill_volume(self, x1, y1, z1, x2, y2, z2):
        dx = abs(int(x2) - int(x1)) + 1
        dy = abs(int(y2) - int(y1)) + 1
        dz = abs(int(z2) - int(z1)) + 1
        vol = dx * dy * dz
        if vol > MAX_FILL_VOLUME:
            raise MinecraftBuilder.BuildBoundsError(
                f"Fill volume {vol} exceeds max of {MAX_FILL_VOLUME}. Break into smaller fills."
            )
        if max(dx, dy, dz) > MAX_DIMENSION:
            raise MinecraftBuilder.BuildBoundsError(
                f"Fill dimension {max(dx, dy, dz)} exceeds max of {MAX_DIMENSION}"
            )

    def place_block(self, x, y, z, block):
        self._add_command(f"/setblock {int(x)} {int(y)} {int(z)} {block}")

    def fill(self, x1, y1, z1, x2, y2, z2, block, mode="replace"):
        self._check_fill_volume(x1, y1, z1, x2, y2, z2)
        self._add_command(f"/fill {int(x1)} {int(y1)} {int(z1)} {int(x2)} {int(y2)} {int(z2)} {block} {mode}")

    def fill_hollow(self, x1, y1, z1, x2, y2, z2, block):
        self.fill(x1, y1, z1, x2, y2, z2, block, "hollow")

    def fill_outline(self, x1, y1, z1, x2, y2, z2, block):
        self.fill(x1, y1, z1, x2, y2, z2, block, "outline")

    def fill_replace(self, x1, y1, z1, x2, y2, z2, block, replace_block):
        self._check_fill_volume(x1, y1, z1, x2, y2, z2)
        self._add_command(f"/fill {int(x1)} {int(y1)} {int(z1)} {int(x2)} {int(y2)} {int(z2)} {block} replace {replace_block}")

    def wall(self, x1, y1, z1, x2, y2, z2, block):
        self.fill(x1, y1, z1, x2, y2, z2, block)

    def floor(self, x1, y1, z1, x2, z2, block):
        self.fill(x1, y1, z1, x2, y1, z2, block)

    def box(self, x, y, z, width, height, depth, block, hollow=True):
        if max(width, height, depth) > MAX_DIMENSION:
            raise MinecraftBuilder.BuildBoundsError(
                f"Box dimension {max(width, height, depth)} exceeds max of {MAX_DIMENSION}"
            )
        x2 = x + width - 1
        y2 = y + height - 1
        z2 = z + depth - 1
        if hollow:
            self.fill_hollow(x, y, z, x2, y2, z2, block)
        else:
            self.fill(x, y, z, x2, y2, z2, block)

    def cylinder(self, cx, cy, cz, radius, height, block, hollow=True, axis="y"):
        self._check_radius(radius)
        if height > MAX_DIMENSION:
            raise MinecraftBuilder.BuildBoundsError(f"Height {height} exceeds max of {MAX_DIMENSION}")
        for h in range(height):
            for dx in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    dist = math.sqrt(dx * dx + dz * dz)
                    if hollow:
                        if radius - 1 < dist <= radius:
                            if axis == "y":
                                self.place_block(cx + dx, cy + h, cz + dz, block)
                            elif axis == "x":
                                self.place_block(cx + h, cy + dx, cz + dz, block)
                            else:
                                self.place_block(cx + dx, cy + dz, cz + h, block)
                    else:
                        if dist <= radius:
                            if axis == "y":
                                self.place_block(cx + dx, cy + h, cz + dz, block)
                            elif axis == "x":
                                self.place_block(cx + h, cy + dx, cz + dz, block)
                            else:
                                self.place_block(cx + dx, cy + dz, cz + h, block)

    def sphere(self, cx, cy, cz, radius, block, hollow=True):
        self._check_radius(radius)
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
                    if hollow:
                        if radius - 1 < dist <= radius:
                            self.place_block(cx + dx, cy + dy, cz + dz, block)
                    else:
                        if dist <= radius:
                            self.place_block(cx + dx, cy + dy, cz + dz, block)

    def dome(self, cx, cy, cz, radius, block, hollow=True):
        self._check_radius(radius)
        for dx in range(-radius, radius + 1):
            for dy in range(0, radius + 1):
                for dz in range(-radius, radius + 1):
                    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
                    if hollow:
                        if radius - 1 < dist <= radius:
                            self.place_block(cx + dx, cy + dy, cz + dz, block)
                    else:
                        if dist <= radius:
                            self.place_block(cx + dx, cy + dy, cz + dz, block)

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
            self.place_block(x, y, z, block)

    def circle(self, cx, cy, cz, radius, block, axis="y"):
        self._check_radius(radius)
        for angle in range(360):
            rad = math.radians(angle)
            if axis == "y":
                x = round(cx + radius * math.cos(rad))
                z = round(cz + radius * math.sin(rad))
                self.place_block(x, cy, z, block)
            elif axis == "x":
                y = round(cy + radius * math.cos(rad))
                z = round(cz + radius * math.sin(rad))
                self.place_block(cx, y, z, block)
            else:
                x = round(cx + radius * math.cos(rad))
                y = round(cy + radius * math.sin(rad))
                self.place_block(x, y, cz, block)

    def arc(self, cx, cy, cz, radius, start_angle, end_angle, block, axis="y"):
        self._check_radius(radius)
        for angle in range(start_angle, end_angle + 1):
            rad = math.radians(angle)
            if axis == "y":
                x = round(cx + radius * math.cos(rad))
                z = round(cz + radius * math.sin(rad))
                self.place_block(x, cy, z, block)

    def spiral(self, cx, cy, cz, radius, height, block, turns=1):
        self._check_radius(radius)
        if height > MAX_DIMENSION:
            raise MinecraftBuilder.BuildBoundsError(f"Height {height} exceeds max of {MAX_DIMENSION}")
        steps = height * 16
        for i in range(steps):
            t = i / steps
            angle = t * turns * 2 * math.pi
            x = round(cx + radius * math.cos(angle))
            z = round(cz + radius * math.sin(angle))
            y = round(cy + t * height)
            self.place_block(x, y, z, block)

    def pyramid(self, cx, cy, cz, base_size, block, hollow=True):
        if base_size > MAX_DIMENSION:
            raise MinecraftBuilder.BuildBoundsError(f"Pyramid base {base_size} exceeds max of {MAX_DIMENSION}")
        for layer in range(base_size // 2 + 1):
            half = base_size // 2 - layer
            x1 = cx - half
            z1 = cz - half
            x2 = cx + half
            z2 = cz + half
            y = cy + layer
            if hollow and layer < base_size // 2:
                for x in range(x1, x2 + 1):
                    self.place_block(x, y, z1, block)
                    self.place_block(x, y, z2, block)
                for z in range(z1 + 1, z2):
                    self.place_block(x1, y, z, block)
                    self.place_block(x2, y, z, block)
            else:
                self.fill(x1, y, z1, x2, y, z2, block)

    def stairs(self, x, y, z, length, direction, block):
        if length > MAX_DIMENSION:
            raise MinecraftBuilder.BuildBoundsError(f"Stairs length {length} exceeds max of {MAX_DIMENSION}")
        for i in range(length):
            if direction == "north":
                self.place_block(x, y + i, z - i, block)
            elif direction == "south":
                self.place_block(x, y + i, z + i, block)
            elif direction == "east":
                self.place_block(x + i, y + i, z, block)
            elif direction == "west":
                self.place_block(x - i, y + i, z, block)

    def clear_area(self, x1, y1, z1, x2, y2, z2):
        self.fill(x1, y1, z1, x2, y2, z2, "air")

    def get_commands(self):
        return self.commands

    def reset(self):
        self.commands = []
