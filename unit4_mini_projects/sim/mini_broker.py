#!/usr/bin/env python3
"""
mini_broker.py - a tiny MQTT 3.1.1 broker for OFFLINE testing of the lab scripts.

Supports: QoS 0/1 (QoS 2 subscriptions are granted as QoS 1), retained messages,
Last Will and Testament (published on any non-clean disconnect, including
keep-alive expiry at 1.5 x keepalive), and the + and # topic wildcards.
Use a real Mosquitto broker for the actual submission if you have one; the lab
scripts are written against the standard paho-mqtt API and run unchanged on both.

Usage:  python3 mini_broker.py [port]      (default 1883)
"""
import socket, sys, threading, time

def log(msg):
    print(f"[broker {time.strftime('%H:%M:%S')}] {msg}", flush=True)

def enc_str(s):
    b = s.encode() if isinstance(s, str) else s
    return len(b).to_bytes(2, "big") + b

def enc_len(n):
    out = bytearray()
    while True:
        d, n = n % 128, n // 128
        out.append(d | 0x80 if n else d)
        if not n:
            return bytes(out)

def recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("closed")
        buf += chunk
    return buf

def read_packet(sock):
    first = recv_exact(sock, 1)[0]
    mult, length = 1, 0
    while True:
        b = recv_exact(sock, 1)[0]
        length += (b & 127) * mult
        if not b & 128:
            break
        mult *= 128
    return first, (recv_exact(sock, length) if length else b"")

def topic_matches(flt, topic):
    f, t = flt.split("/"), topic.split("/")
    for i, seg in enumerate(f):
        if seg == "#":
            return True
        if i >= len(t) or (seg != "+" and seg != t[i]):
            return False
    return len(f) == len(t)

def read_str(buf, i):
    n = int.from_bytes(buf[i:i + 2], "big")
    return buf[i + 2:i + 2 + n], i + 2 + n

class Session:
    def __init__(self, sock):
        self.sock, self.id, self.subs = sock, "", {}
        self.keepalive, self.last, self.will, self.taken = 0, time.time(), None, False
        self.wlock, self.pid = threading.Lock(), 0

    def send(self, data):
        try:
            with self.wlock:
                self.sock.sendall(data)
        except OSError:
            pass

    def next_pid(self):
        self.pid = self.pid % 65535 + 1
        return self.pid

class Broker:
    def __init__(self, host="0.0.0.0", port=1883):
        self.host, self.port = host, port
        self.sessions, self.retained = {}, {}
        self.lock = threading.RLock()

    def serve(self):
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(50)
        log(f"listening on {self.host}:{self.port}")
        threading.Thread(target=self.watchdog, daemon=True).start()
        while True:
            sock, _ = srv.accept()
            threading.Thread(target=self.handle, args=(sock,), daemon=True).start()

    def watchdog(self):
        while True:
            time.sleep(1)
            now = time.time()
            with self.lock:
                for s in list(self.sessions.values()):
                    if s.keepalive and now - s.last > 1.5 * s.keepalive:
                        log(f"keep-alive expired for '{s.id}' -> closing connection")
                        try:
                            s.sock.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass

    def handle(self, sock):
        sess, clean = None, False
        try:
            first, body = read_packet(sock)
            if first >> 4 != 1:
                return
            sess = self.on_connect(sock, body)
            while True:
                first, body = read_packet(sock)
                sess.last = time.time()
                ptype = first >> 4
                if ptype == 3:
                    self.on_publish(sess, first, body)
                elif ptype == 8:
                    self.on_subscribe(sess, body)
                elif ptype == 10:
                    sess.send(b"\xb0\x02" + body[:2])
                elif ptype == 12:
                    sess.send(b"\xd0\x00")
                elif ptype == 14:
                    clean = True
                    break
        except (ConnectionError, OSError):
            pass
        finally:
            self.drop(sess, sock, clean)

    def on_connect(self, sock, b):
        _, i = read_str(b, 0)                      # protocol name
        flags = b[i + 1]
        keepalive = int.from_bytes(b[i + 2:i + 4], "big")
        cid, i = read_str(b, i + 4)
        s = Session(sock)
        s.id, s.keepalive = cid.decode() or f"auto-{id(s)}", keepalive
        if flags & 0x04:
            wt, i = read_str(b, i)
            wm, i = read_str(b, i)
            s.will = (wt.decode(), wm, (flags >> 3) & 3, bool(flags & 0x20))
        with self.lock:
            old = self.sessions.get(s.id)
            if old:
                old.taken = True
                try:
                    old.sock.close()
                except OSError:
                    pass
            self.sessions[s.id] = s
        s.send(b"\x20\x02\x00\x00")
        log(f"CONNECT '{s.id}' keepalive={keepalive}s will={'yes -> ' + s.will[0] if s.will else 'no'}")
        return s

    def on_publish(self, sess, first, b):
        qos, retain = (first >> 1) & 3, bool(first & 1)
        topic, i = read_str(b, 0)
        topic = topic.decode()
        if qos:
            pid = b[i:i + 2]
            i += 2
            sess.send(b"\x40\x02" + pid)           # PUBACK
        payload = b[i:]
        log(f"PUBLISH '{sess.id}' {topic} qos={qos} retain={int(retain)} payload={payload[:40]!r}")
        self.route(topic, payload, qos, retain)

    def route(self, topic, payload, qos, retain):
        with self.lock:
            if retain:
                if payload:
                    self.retained[topic] = (payload, qos)
                else:
                    self.retained.pop(topic, None)
            for s in list(self.sessions.values()):
                grants = [q for f, q in s.subs.items() if topic_matches(f, topic)]
                if grants:
                    self.deliver(s, topic, payload, min(qos, max(grants)), False)

    def deliver(self, s, topic, payload, qos, retained_flag):
        hdr = 0x30 | (qos << 1) | (1 if retained_flag else 0)
        body = enc_str(topic) + (s.next_pid().to_bytes(2, "big") if qos else b"") + payload
        s.send(bytes([hdr]) + enc_len(len(body)) + body)

    def on_subscribe(self, sess, b):
        pid, i, granted, new = b[:2], 2, b"", []
        while i < len(b):
            f, i = read_str(b, i)
            q = min(b[i], 1)
            i += 1
            sess.subs[f.decode()] = q
            granted += bytes([q])
            new.append(f.decode())
        sess.send(b"\x90" + enc_len(2 + len(granted)) + pid + granted)
        log(f"SUBSCRIBE '{sess.id}' {new}")
        with self.lock:
            for t, (pl, q) in list(self.retained.items()):
                for f in new:
                    if topic_matches(f, t):
                        log(f"  -> delivering retained {t} to '{sess.id}'")
                        self.deliver(sess, t, pl, min(q, sess.subs[f]), True)
                        break

    def drop(self, sess, sock, clean):
        try:
            sock.close()
        except OSError:
            pass
        if sess is None:
            return
        with self.lock:
            if self.sessions.get(sess.id) is sess:
                del self.sessions[sess.id]
        if clean:
            log(f"DISCONNECT '{sess.id}' (clean) - will NOT be published")
        elif sess.will and not sess.taken:
            t, m, q, r = sess.will
            log(f"UNCLEAN DISCONNECT '{sess.id}' -> publishing LWT {t} = {m!r} (qos={q}, retain={int(r)})")
            self.route(t, m, q, r)

if __name__ == "__main__":
    Broker(port=int(sys.argv[1]) if len(sys.argv) > 1 else 1883).serve()
