import ast

MAX_BLOCKS = 500000

SAFE_BUILTINS = {
    "range": range,
    "len": len,
    "int": int,
    "float": float,
    "abs": abs,
    "min": min,
    "max": max,
    "round": round,
    "print": print,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "str": str,
    "bool": bool,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "True": True,
    "False": False,
    "None": None,
}


class BuildContext:
    def __init__(self, plot_origin, plot_bounds):
        self._origin_x = plot_origin["x"]
        self._origin_y = plot_origin["y"]
        self._origin_z = plot_origin["z"]
        self._bounds_x1 = plot_bounds["x1"]
        self._bounds_z1 = plot_bounds["z1"]
        self._bounds_x2 = plot_bounds["x2"]
        self._bounds_z2 = plot_bounds["z2"]
        self.commands = []
        self.block_count = 0

    def _check_limit(self, count=1):
        if self.block_count + count > MAX_BLOCKS:
            raise RuntimeError(f"Block limit exceeded: {self.block_count + count} > {MAX_BLOCKS}")

    def _in_bounds(self, world_x, world_z):
        return (self._bounds_x1 <= world_x <= self._bounds_x2 and
                self._bounds_z1 <= world_z <= self._bounds_z2)

    def setblock(self, x, y, z, block):
        world_x = self._origin_x + x
        world_y = self._origin_y + y
        world_z = self._origin_z + z
        if not self._in_bounds(world_x, world_z):
            return
        self._check_limit(1)
        self.block_count += 1
        self.commands.append(f"/setblock {world_x} {world_y} {world_z} {block}")

    def fill(self, x1, y1, z1, x2, y2, z2, block):
        world_x1 = self._origin_x + x1
        world_y1 = self._origin_y + y1
        world_z1 = self._origin_z + z1
        world_x2 = self._origin_x + x2
        world_y2 = self._origin_y + y2
        world_z2 = self._origin_z + z2
        min_wx = min(world_x1, world_x2)
        max_wx = max(world_x1, world_x2)
        min_wz = min(world_z1, world_z2)
        max_wz = max(world_z1, world_z2)
        if max_wx < self._bounds_x1 or min_wx > self._bounds_x2:
            return
        if max_wz < self._bounds_z1 or min_wz > self._bounds_z2:
            return
        clamped_x1 = max(min_wx, self._bounds_x1)
        clamped_x2 = min(max_wx, self._bounds_x2)
        clamped_z1 = max(min_wz, self._bounds_z1)
        clamped_z2 = min(max_wz, self._bounds_z2)
        clamped_y1 = min(world_y1, world_y2)
        clamped_y2 = max(world_y1, world_y2)
        volume = (clamped_x2 - clamped_x1 + 1) * (clamped_y2 - clamped_y1 + 1) * (clamped_z2 - clamped_z1 + 1)
        self._check_limit(volume)
        self.block_count += volume
        self.commands.append(f"/fill {clamped_x1} {clamped_y1} {clamped_z1} {clamped_x2} {clamped_y2} {clamped_z2} {block}")

    def clear(self):
        plot_width_x = self._bounds_x2 - self._bounds_x1
        plot_width_z = self._bounds_z2 - self._bounds_z1
        self.fill(0, 0, 0, plot_width_x, 120, plot_width_z, "minecraft:air")


def validate_script_ast(script):
    try:
        tree = ast.parse(script)
    except SyntaxError as e:
        return False, f"Syntax error: {str(e)}"
    
    forbidden_calls = {
        "exec", "eval", "compile", "__import__", "open", 
        "getattr", "setattr", "delattr", "globals", "locals", 
        "vars", "dir", "type", "breakpoint", "input"
    }
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("__") or node.attr.endswith("__"):
                return False, f"Access to dunder attribute '{node.attr}' is not allowed"
        
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            return False, "Imports are not allowed"
        
        elif isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            
            if func_name in forbidden_calls:
                return False, f"Call to '{func_name}' is not allowed"
    
    return True, None


def execute_build_script(script, plot_origin, plot_bounds):
    is_valid, error_msg = validate_script_ast(script)
    if not is_valid:
        return {
            "success": False,
            "commands": [],
            "block_count": 0,
            "error": error_msg,
        }
    
    try:
        build = BuildContext(plot_origin, plot_bounds)
        restricted_globals = {"__builtins__": SAFE_BUILTINS, "build": build}
        exec(script, restricted_globals)
        return {
            "success": True,
            "commands": build.commands,
            "block_count": build.block_count,
            "error": None,
        }
    except Exception as e:
        return {
            "success": False,
            "commands": [],
            "block_count": 0,
            "error": f"{type(e).__name__}: {str(e)}",
        }
