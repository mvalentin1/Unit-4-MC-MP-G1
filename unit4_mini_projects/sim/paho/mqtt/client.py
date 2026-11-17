"""
Minimal stand-in for paho-mqtt (v2 API subset) so the lab scripts can run in an
environment where `pip install paho-mqtt` is impossible. It speaks real MQTT 3.1.1
over TCP. On your own machine, `pip install paho-mqtt` and DO NOT put this folder on
PYTHONPATH - the scripts use only the public paho API.
"""
import select, socket, threading, time

class CallbackAPIVersion:
    VERSION1, VERSION2 = 1, 2

MQTT_ERR_SUCCESS, MQTT_ERR_NO_CONN = 0, 4

def _s(x):
    b = x.encode() if isinstance(x, str) else x
    return len(b).to_bytes(2, "big") + b

def _len(n):
    out = bytearray()
    while True:
        d, n = n % 128, n // 128
        out.append(d | 0x80 if n else d)
        if not n:
            return bytes(out)

def _exact(sock, n):
    buf = b""
    while len(buf) < n:
        c = sock.recv(n - len(buf))
        if not c:
            raise ConnectionError
        buf += c
    return buf

class MQTTMessage:
    def __init__(self, topic, payload, qos, retain, mid):
        self.topic, self.payload, self.qos, self.retain, self.mid = topic, payload, qos, retain, mid

class MQTTMessageInfo:
    def __init__(self, rc, mid):
        self.rc, self.mid = rc, mid
    def wait_for_publish(self, timeout=None):
        return None
    def is_published(self):
        return True

class Client:
    def __init__(self, callback_api_version=None, client_id="", **kw):
        if isinstance(callback_api_version, str):
            client_id = callback_api_version
            callback_api_version = CallbackAPIVersion.VERSION1
        self._v2 = callback_api_version == CallbackAPIVersion.VERSION2
        self._id, self._will, self._sock = client_id, None, None
        self._keepalive, self._mid, self._stop = 60, 0, False
        self._wlock, self._thread = threading.Lock(), None
        self.on_connect = self.on_message = self.on_disconnect = None
        self.userdata = None

    def will_set(self, topic, payload=None, qos=0, retain=False):
        self._will = (topic, payload.encode() if isinstance(payload, str) else (payload or b""), qos, retain)

    def connect(self, host, port=1883, keepalive=60):
        self._keepalive = keepalive
        self._sock = socket.create_connection((host, port), timeout=10)
        self._sock.settimeout(None)
        flags = 0x02
        payload = _s(self._id)
        if self._will:
            t, m, q, r = self._will
            flags |= 0x04 | (q << 3) | (0x20 if r else 0)
            payload += _s(t) + _s(m)
        var = _s("MQTT") + bytes([4, flags]) + keepalive.to_bytes(2, "big")
        body = var + payload
        self._last_tx = time.time()
        self._send(b"\x10" + _len(len(body)) + body)
        return MQTT_ERR_SUCCESS

    def _send(self, data):
        with self._wlock:
            self._sock.sendall(data)
            self._last_tx = time.time()

    def _mid_next(self):
        self._mid = self._mid % 65535 + 1
        return self._mid

    def publish(self, topic, payload=None, qos=0, retain=False):
        p = payload.encode() if isinstance(payload, str) else (payload or b"")
        if not self._sock:
            return MQTTMessageInfo(MQTT_ERR_NO_CONN, 0)
        mid = self._mid_next() if qos else 0
        body = _s(topic) + (mid.to_bytes(2, "big") if qos else b"") + p
        try:
            self._send(bytes([0x30 | (qos << 1) | int(retain)]) + _len(len(body)) + body)
        except OSError:
            return MQTTMessageInfo(MQTT_ERR_NO_CONN, mid)
        return MQTTMessageInfo(MQTT_ERR_SUCCESS, mid)

    def subscribe(self, topic, qos=0):
        pairs = [(topic, qos)] if isinstance(topic, str) else list(topic)
        mid = self._mid_next()
        body = mid.to_bytes(2, "big") + b"".join(_s(t) + bytes([q]) for t, q in pairs)
        self._send(b"\x82" + _len(len(body)) + body)
        return (MQTT_ERR_SUCCESS, mid)

    def disconnect(self):
        self._stop = True
        try:
            self._send(b"\xe0\x00")
            self._sock.close()
        except OSError:
            pass

    def loop_start(self):
        self._thread = threading.Thread(target=self.loop_forever, daemon=True)
        self._thread.start()

    def loop_stop(self):
        self._stop = True

    def loop_forever(self):
        try:
            while not self._stop:
                r, _, _ = select.select([self._sock], [], [], 0.5)
                if r:
                    self._handle(*self._read())
                if time.time() - self._last_tx > self._keepalive / 2:
                    self._send(b"\xc0\x00")
        except (ConnectionError, OSError, ValueError):
            pass
        if self.on_disconnect and not self._stop:
            args = (self, self.userdata, None, 0, None) if self._v2 else (self, self.userdata, 1)
            self.on_disconnect(*args)

    def _read(self):
        first = _exact(self._sock, 1)[0]
        mult, n = 1, 0
        while True:
            b = _exact(self._sock, 1)[0]
            n += (b & 127) * mult
            if not b & 128:
                break
            mult *= 128
        return first, (_exact(self._sock, n) if n else b"")

    def _handle(self, first, body):
        t = first >> 4
        if t == 2 and self.on_connect:
            if self._v2:
                self.on_connect(self, self.userdata, {}, body[1], None)
            else:
                self.on_connect(self, self.userdata, {}, body[1])
        elif t == 3:
            qos = (first >> 1) & 3
            tl = int.from_bytes(body[:2], "big")
            topic, i = body[2:2 + tl].decode(), 2 + tl
            mid = 0
            if qos:
                mid = int.from_bytes(body[i:i + 2], "big")
                i += 2
                self._send(b"\x40\x02" + mid.to_bytes(2, "big"))
            if self.on_message:
                self.on_message(self, self.userdata, MQTTMessage(topic, body[i:], qos, bool(first & 1), mid))
