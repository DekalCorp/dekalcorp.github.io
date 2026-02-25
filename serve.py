#!/usr/bin/env python3
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import argparse
import json
import os
import time

WATCH_EXTENSIONS = {".html", ".css", ".js", ".json", ".svg", ".png", ".jpg"}
LIVE_RELOAD_SCRIPT = """
<script>
(function() {
  let lastMtime = 0;
  async function poll() {
    try {
      const res = await fetch("/__livereload");
      const data = await res.json();
      if (lastMtime && data.mtime > lastMtime) location.reload();
      lastMtime = data.mtime;
    } catch {}
    setTimeout(poll, 500);
  }
  poll();
})();
</script>
"""


def get_max_mtime(directory):
    max_mtime = 0
    for root, _, files in os.walk(directory):
        if root.startswith(os.path.join(directory, ".git")):
            continue
        for f in files:
            if os.path.splitext(f)[1].lower() in WATCH_EXTENSIONS:
                try:
                    mt = os.path.getmtime(os.path.join(root, f))
                    if mt > max_mtime:
                        max_mtime = mt
                except OSError:
                    pass
    return max_mtime


class LiveReloadHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/__livereload":
            mtime = get_max_mtime(os.getcwd())
            payload = json.dumps({"mtime": mtime}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
            return

        # For HTML files, read the content, inject the script, and send with correct length
        f = self.send_head()
        if f:
            content = f.read()
            f.close()
            ctype = self.headers_sent_content_type or ""
            if "text/html" in ctype:
                if b"</body>" in content:
                    content = content.replace(b"</body>", LIVE_RELOAD_SCRIPT.encode() + b"</body>")
                else:
                    content += LIVE_RELOAD_SCRIPT.encode()
            self.wfile.write(content)

    def send_head(self):
        self.headers_sent_content_type = ""
        f = super().send_head()
        return f

    def send_header(self, keyword, value):
        if keyword.lower() == "content-type":
            self.headers_sent_content_type = value
        # Skip Content-Length from parent — we'll send the full body directly
        if keyword.lower() == "content-length" and "text/html" in getattr(self, "headers_sent_content_type", ""):
            return
        super().send_header(keyword, value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the site locally.")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to.")
    parser.add_argument("--port", type=int, default=8000, help="Port to serve on.")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), LiveReloadHandler)
    print(f"Serving on http://{args.host}:{args.port} (live reload enabled)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
