import json, ssl, sys, http.server
SC = json.load(open(sys.argv[1]))
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_GET(self):
        if self.headers.get("Authorization") != "Bearer good":
            self.send_response(401); self.end_headers(); return
        p = self.path.split("?")[0].replace("/api/v2","")
        if p not in SC: self.send_response(404); self.end_headers(); return
        b = json.dumps({"results": SC[p]}).encode()
        self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers(); self.wfile.write(b)
s = http.server.HTTPServer(("127.0.0.1", int(sys.argv[2])), H)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain(sys.argv[3], sys.argv[4])
s.socket = ctx.wrap_socket(s.socket, server_side=True); s.serve_forever()
