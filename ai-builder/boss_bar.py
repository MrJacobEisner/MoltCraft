import threading
import time
import math


COLORS = ["yellow", "green", "blue", "purple", "pink", "red", "white"]
PULSE_PERIOD = 2.0
UPDATE_INTERVAL = 0.3


class BossBarManager:
    def __init__(self, rcon, player_name):
        self.rcon = rcon
        self.player_name = player_name
        self.bar_id = f"ai_build_{player_name.lower()}"
        self._thread = None
        self._running = False
        self._phase_text = "Thinking..."
        self._color_index = 0

    def start(self, text="Thinking..."):
        self._phase_text = text
        self._running = True
        self._create_bar()
        self._thread = threading.Thread(target=self._animate_loop, daemon=True)
        self._thread.start()

    def set_phase(self, text, color=None):
        self._phase_text = text
        if color:
            self._set_color(color)
        self._set_name(text)

    def complete(self, text="Build complete!", sound=True):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        self._set_name(text)
        self._set_color("green")
        self._set_value(100)
        if sound:
            self._play_sound("entity.player.levelup")
        time.sleep(1.5)
        self._remove_bar()

    def fail(self, text="Build failed"):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        self._set_name(text)
        self._set_color("red")
        self._set_value(100)
        self._play_sound("block.note_block.bass")
        time.sleep(1.5)
        self._remove_bar()

    def cancel(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        self._remove_bar()

    def _animate_loop(self):
        start = time.time()
        color_switch_time = start
        while self._running:
            elapsed = time.time() - start
            value = int((math.sin(elapsed * math.pi / PULSE_PERIOD) + 1) * 50)
            self._set_value(value)

            if time.time() - color_switch_time > PULSE_PERIOD:
                self._color_index = (self._color_index + 1) % len(COLORS)
                self._set_color(COLORS[self._color_index])
                color_switch_time = time.time()

            time.sleep(UPDATE_INTERVAL)

    def _create_bar(self):
        self._cmd(f'bossbar add minecraft:{self.bar_id} "{self._phase_text}"')
        self._cmd(f'bossbar set minecraft:{self.bar_id} players {self.player_name}')
        self._cmd(f'bossbar set minecraft:{self.bar_id} color yellow')
        self._cmd(f'bossbar set minecraft:{self.bar_id} visible true')
        self._cmd(f'bossbar set minecraft:{self.bar_id} value 0')
        self._cmd(f'bossbar set minecraft:{self.bar_id} max 100')

    def _remove_bar(self):
        self._cmd(f'bossbar remove minecraft:{self.bar_id}')

    def _set_value(self, value):
        self._cmd(f'bossbar set minecraft:{self.bar_id} value {max(0, min(100, value))}')

    def _set_color(self, color):
        self._cmd(f'bossbar set minecraft:{self.bar_id} color {color}')

    def _set_name(self, text):
        self._cmd(f'bossbar set minecraft:{self.bar_id} name "{text}"')

    def _play_sound(self, sound):
        self._cmd(f'playsound minecraft:{sound} master {self.player_name} ~ ~ ~ 1 1')

    def _cmd(self, command):
        try:
            self.rcon.command(command)
        except Exception:
            pass
