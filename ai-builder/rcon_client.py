import socket
import struct
import time


class RconClient:
    def __init__(self, host="localhost", port=25575, password="minecraft-ai-builder"):
        self.host = host
        self.port = port
        self.password = password
        self.sock = None
        self.request_id = 0

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(10)
        self.sock.connect((self.host, self.port))
        self._send_packet(3, self.password)
        response = self._read_packet()
        if response["id"] == -1:
            raise Exception("RCON authentication failed")
        return True

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def command(self, cmd):
        if not self.sock:
            self.connect()
        self._send_packet(2, cmd)
        response = self._read_packet()
        return response["payload"]

    def _send_packet(self, packet_type, payload):
        self.request_id += 1
        data = struct.pack("<ii", self.request_id, packet_type) + payload.encode("utf-8") + b"\x00\x00"
        packet = struct.pack("<i", len(data)) + data
        self.sock.sendall(packet)

    def _read_packet(self):
        raw_len = self._recv_exact(4)
        length = struct.unpack("<i", raw_len)[0]
        data = self._recv_exact(length)
        request_id = struct.unpack("<i", data[0:4])[0]
        packet_type = struct.unpack("<i", data[4:8])[0]
        payload = data[8:-2].decode("utf-8")
        return {"id": request_id, "type": packet_type, "payload": payload}

    def _recv_exact(self, n):
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("Connection closed")
            data += chunk
        return data

    def send_commands(self, commands, delay=0.05):
        results = []
        for cmd in commands:
            try:
                result = self.command(cmd)
                results.append(result)
                if delay > 0:
                    time.sleep(delay)
            except Exception as e:
                results.append(f"Error: {e}")
                try:
                    self.disconnect()
                    self.connect()
                except:
                    pass
        return results
