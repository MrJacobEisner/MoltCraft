import math


class MinecraftBuilder:
    def __init__(self):
        self.commands = []

    def place_block(self, x, y, z, block):
        self.commands.append(f"/setblock {x} {y} {z} {block}")

    def fill(self, x1, y1, z1, x2, y2, z2, block, mode="replace"):
        self.commands.append(f"/fill {x1} {y1} {z1} {x2} {y2} {z2} {block} {mode}")

    def fill_hollow(self, x1, y1, z1, x2, y2, z2, block):
        self.fill(x1, y1, z1, x2, y2, z2, block, "hollow")

    def fill_outline(self, x1, y1, z1, x2, y2, z2, block):
        self.fill(x1, y1, z1, x2, y2, z2, block, "outline")

    def fill_replace(self, x1, y1, z1, x2, y2, z2, block, replace_block):
        self.commands.append(f"/fill {x1} {y1} {z1} {x2} {y2} {z2} {block} replace {replace_block}")

    def wall(self, x1, y1, z1, x2, y2, z2, block):
        self.fill(x1, y1, z1, x2, y2, z2, block)

    def floor(self, x1, y1, z1, x2, z2, block):
        self.fill(x1, y1, z1, x2, y1, z2, block)

    def box(self, x, y, z, width, height, depth, block, hollow=True):
        x2 = x + width - 1
        y2 = y + height - 1
        z2 = z + depth - 1
        if hollow:
            self.fill_hollow(x, y, z, x2, y2, z2, block)
        else:
            self.fill(x, y, z, x2, y2, z2, block)

    def cylinder(self, cx, cy, cz, radius, height, block, hollow=True, axis="y"):
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
        for i in range(steps + 1):
            t = i / steps if steps > 0 else 0
            x = round(x1 + dx * t)
            y = round(y1 + dy * t)
            z = round(z1 + dz * t)
            self.place_block(x, y, z, block)

    def circle(self, cx, cy, cz, radius, block, axis="y"):
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
        for angle in range(start_angle, end_angle + 1):
            rad = math.radians(angle)
            if axis == "y":
                x = round(cx + radius * math.cos(rad))
                z = round(cz + radius * math.sin(rad))
                self.place_block(x, cy, z, block)

    def spiral(self, cx, cy, cz, radius, height, block, turns=1):
        steps = height * 16
        for i in range(steps):
            t = i / steps
            angle = t * turns * 2 * math.pi
            x = round(cx + radius * math.cos(angle))
            z = round(cz + radius * math.sin(angle))
            y = round(cy + t * height)
            self.place_block(x, y, z, block)

    def pyramid(self, cx, cy, cz, base_size, block, hollow=True):
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
