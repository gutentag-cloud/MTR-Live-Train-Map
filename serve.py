#!/usr/bin/env python3
import http.server, socketserver, webbrowser, threading
PORT=8080
threading.Timer(0.8, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
with socketserver.TCPServer(("127.0.0.1",PORT),http.server.SimpleHTTPRequestHandler) as httpd:
    print(f"HK Train Display running at http://localhost:{PORT}")
    httpd.serve_forever()
