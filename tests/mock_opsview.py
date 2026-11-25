import json, http.server
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def _j(self,o): b=json.dumps(o).encode(); self.send_response(200); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        n=int(self.headers["Content-Length"]); d=json.loads(self.rfile.read(n))
        self._j({"token":"abc"} if d["password"]=="pw" else {})
    def do_GET(self):
        assert self.headers["X-Opsview-Token"]=="abc"
        self._j({"list":[{"name":"fw-x","hosttemplates":[{"name":"FortiGate - Base"},{"name":"FortiGate - HA"},{"name":"FortiGate - SD-WAN"},{"name":"FortiGate - FortiSwitch"},{"name":"FortiGate - FortiAP"}]}]})
http.server.HTTPServer(("127.0.0.1",int(__import__("sys").argv[1])),H).serve_forever()
