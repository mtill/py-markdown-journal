#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
import json
from pathlib import Path
import sqlite3
from noteslib import parseEntries, MARKDOWN_SUFFIX, TAG_NAMESPACE_SEPARATOR
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote, urlparse


DB_VERSION = "1_2"
BACKLINKS_FILENAME = ".backlinks_v" + DB_VERSION + ".sqlite"


class BacklinkEngine:
    def __init__(self, notebookpath):
        self.notebookpath = notebookpath
        self.db_path = notebookpath / BACKLINKS_FILENAME
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    path TEXT PRIMARY KEY,
                    last_mtime REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS backlinks (
                    source TEXT,
                    target TEXT,
                    PRIMARY KEY (source, target)
                )
            """)

    def get_backlinks(self, file_path):
        results = []

        lt = file_path
        if lt.startswith("/"):
            lt = lt[1:]
        lt = (self.notebookpath / lt).relative_to(self.notebookpath).as_posix()
        if lt.endswith(MARKDOWN_SUFFIX):
            lt = lt[:-len(MARKDOWN_SUFFIX)]

        lt = lt.replace("/", TAG_NAMESPACE_SEPARATOR).lower()


        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT source FROM backlinks 
                WHERE target = ?""", (lt, ))

            results = [row[0] for row in cursor.fetchall()]

        return sorted(results)

    @staticmethod
    def normalize_note_key(path):
        norm = path
        if norm.startswith("/"):
            norm = norm[1:]
        if norm.endswith(MARKDOWN_SUFFIX):
            norm = norm[:-len(MARKDOWN_SUFFIX)]
        return norm.replace("/", TAG_NAMESPACE_SEPARATOR).lower()

    def get_graph_data(self):
        with sqlite3.connect(self.db_path) as conn:
            backlink_rows = conn.execute("SELECT source, target FROM backlinks").fetchall()
            file_rows = conn.execute("SELECT path FROM files").fetchall()

        normalized_files = {}
        nodes = {}
        edges = []

        for (file_path,) in file_rows:
            node_id = self.normalize_note_key(file_path)
            normalized_files[node_id] = file_path
            nodes[node_id] = {
                "id": node_id,
                "label": file_path.lstrip("/"),
                "title": file_path,
                "group": "file"
            }

        for source, target in backlink_rows:
            source_id = self.normalize_note_key(source)
            target_id = target

            if source_id not in nodes:
                nodes[source_id] = {
                    "id": source_id,
                    "label": source.lstrip("/"),
                    "title": source,
                    "group": "file"
                }

            if target_id not in nodes:
                if target_id in normalized_files:
                    nodes[target_id] = {
                        "id": target_id,
                        "label": normalized_files[target_id].lstrip("/"),
                        "title": normalized_files[target_id],
                        "group": "file"
                    }
                else:
                    nodes[target_id] = {
                        "id": target_id,
                        "label": target_id,
                        "title": target_id,
                        "group": "tag"
                    }

            edges.append({"source": source_id, "target": target_id})

        return {"nodes": list(nodes.values()), "edges": edges}

    def get_graph_page(self):
        graph_json = json.dumps(self.get_graph_data())
        return """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>link graph</title>

  <!-- Cytoscape core (latest is fine) -->
  <script src="https://unpkg.com/cytoscape/dist/cytoscape.min.js"></script>

  <style>
    html, body {
      width: 100%;
      height: 100%;
      margin: 0;
      padding: 0;
      overflow: hidden;
    }
    #network {
      width: 100vw;
      height: 100vh;
    }
  </style>
</head>

<body>
<div id="network"></div>

<script>
/* ----------------------------------------------------
   LOAD GRAPH DATA
---------------------------------------------------- */
const graphData = {graph_json};

/* ----------------------------------------------------
   COMPUTE IN-DEGREE FOR NODE SIZE
---------------------------------------------------- */
const inDegree = {};
graphData.nodes.forEach(n => inDegree[n.id] = 0);
graphData.edges.forEach(e => inDegree[e.target]++);

/* ----------------------------------------------------
   BUILD CYTOSCAPE ELEMENTS
---------------------------------------------------- */
const elements = [];

// Nodes
graphData.nodes.forEach(node => {
  const incoming = inDegree[node.id] || 0;
  const size = 6 + incoming * 3;

  elements.push({
    data: {
      id: node.id,
      label: node.label,
      group: node.group,
      size,
      color: node.group === "file" ? "#6AA6FF" : "#F8B551"
    }
  });
});

// Edges
graphData.edges.forEach(edge => {
  elements.push({
    data: {
      id: edge.source + "_" + edge.target,
      source: edge.source,
      target: edge.target
    }
  });
});

/* ----------------------------------------------------
   INIT CYTOSCAPE
---------------------------------------------------- */
const cy = cytoscape({
  container: document.getElementById("network"),
  elements: elements,

  style: [
    {
      selector: "node",
      style: {
        "background-color": "data(color)",
        "width": "data(size)",
        "height": "data(size)",
        "label": "data(label)",
        "text-valign": "center",
        "font-size": 7,
        "text-wrap": "wrap",
        "text-max-width": "80px",
        "padding": "6px",
        "color": "#333"
      }
    },
    {
      selector: "edge",
      style: {
        "width": 1,
        "line-color": "#999",
        "target-arrow-color": "#999",
        "target-arrow-shape": "triangle",
        "curve-style": "bezier"
      }
    }
  ],

  /* ----------------------------------------------------
     BUILT-IN COSE LAYOUT (no extensions required)
  ---------------------------------------------------- */
  layout: {
    name: "cose",
    animate: true,
    randomize: true,
    nodeRepulsion: 4000,
    gravity: 10,
    nodeOverlap: 300,
    componentSpacing: 200,
    padding: 70
  }
});

/* ----------------------------------------------------
   CLICK NODE → SHOW DATA
---------------------------------------------------- */
cy.on("tap", "node", evt => {
  console.log(evt.target.data());
});

/* ----------------------------------------------------
   DRAGGING IS BUILT-IN
---------------------------------------------------- */
cy.nodes().grabify();

</script>
</body>
</html>""".replace("{graph_json}", graph_json)

    def extract_links(self, file_path):
        parsedEntries = parseEntries(thepath=file_path, notebookpath=self.notebookpath)
        links = set()
        for t in parsedEntries["prefixTags"]:
            links.add(t)

        for e in parsedEntries["entries"]:
            for t in e["tags"]:
                links.add(t)

        return links

    def sync_file(self, file_path: Path):
        """Updates or adds file links to the DB."""
        if not file_path.exists():
            self.remove_file(file_path)
            return

        mtime = file_path.stat().st_mtime

        with sqlite3.connect(self.db_path) as conn:
            abs_path = "/" + (self.notebookpath / file_path).relative_to(self.notebookpath).as_posix()
            cursor = conn.execute("SELECT last_mtime FROM files WHERE path = ?", (abs_path,))
            row = cursor.fetchone()

            if row and row[0] >= mtime:
                return 

            links = self.extract_links(file_path)
            conn.execute("DELETE FROM backlinks WHERE source = ?", (abs_path,))
            for link in links:
                conn.execute("INSERT OR IGNORE INTO backlinks (source, target) VALUES (?, ?)", 
                             (abs_path, link.lower()))

            conn.execute("INSERT OR REPLACE INTO files (path, last_mtime) VALUES (?, ?)", 
                         (abs_path, mtime))
            print(f"🔄 Synced: {abs_path}")

    def remove_file(self, file_path: Path):
        """Removes file and its associated links from the DB."""
        abs_path = "/" + (self.notebookpath / file_path).relative_to(self.notebookpath).as_posix()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM files WHERE path = ?", (abs_path,))
            conn.execute("DELETE FROM backlinks WHERE source = ?", (abs_path,))
        print(f"🗑️ Removed: {file_path.name}")

    def catch_up(self):
        print("🔍 Scanning for changes...")

        # Update or add existing files
        for md_file in self.notebookpath.rglob("*" + MARKDOWN_SUFFIX):
            self.sync_file(md_file)

        # Clean up files that were deleted while the script was away
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT path FROM files")
            stored_paths = [row[0] for row in cursor.fetchall()]

            for path_str in stored_paths:
                if path_str.startswith("/"):
                    path_str = "." + path_str
                path_file = self.notebookpath / path_str
                if not path_file.exists():
                    self.remove_file(path_file)

        print("✅ Catch-up complete.")


class MarkdownHandler(FileSystemEventHandler):
    def __init__(self, engine: BacklinkEngine):
        self.engine = engine

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(MARKDOWN_SUFFIX):
            self.engine.sync_file(Path(event.src_path))

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(MARKDOWN_SUFFIX):
            self.engine.sync_file(Path(event.src_path))

    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith(MARKDOWN_SUFFIX):
            self.engine.remove_file(Path(event.src_path))


def backlink_handler_factory(engine):
    class BacklinkHandler(BaseHTTPRequestHandler):
        def send_json(self, payload):
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode('utf-8'))

        def send_html(self, html):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))

        def send_file(self, filepath):
            if not Path(filepath).exists():
                self.send_error(404, "File not found")
                return

            # Basic MIME type detection
            if filepath.name.endswith(".html"):
                mime = "text/html"
            elif filepath.name.endswith(".js"):
                mime = "application/javascript"
            elif filepath.name.endswith(".css"):
                mime = "text/css"
            elif filepath.name.endswith(".json"):
                mime = "application/json"
            elif filepath.name.endswith(".png"):
                mime = "image/png"
            elif filepath.name.endswith(".jpg") or filepath.name.endswith(".jpeg"):
                mime = "image/jpeg"
            else:
                mime = "application/octet-stream"

            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.end_headers()

            with open(filepath, "rb") as f:
                self.wfile.write(f.read())

        def do_GET(self):
            parsed_url = urlparse(self.path)
            path = unquote(parsed_url.path)

            # Main graph page
            if path in ('', '/', '/graph', '/graph/'):
                self.send_html(engine.get_graph_page())
                return

            # Graph data
            if path == '/graphdata':
                self.send_json(engine.get_graph_data())
                return

            # NEW: serve static files
            if path.startswith("/static/"):
                filename = path[len("/static/"):]
                # Prevent directory traversal
                if ".." in filename:
                    self.send_error(400, "Invalid path")
                    return

                filepath = Path(__file__).parent / "static" / filename
                self.send_file(filepath)
                return

            # Backlink lookup
            target_path = path.lstrip('/')
            if not target_path:
                self.send_error(400, "Bad Request: Please provide a path (e.g., /file.md)")
                return

            response = engine.get_backlinks(target_path)
            self.send_json(response)

    return BacklinkHandler


def main(notebookpath, host, port, use_polling):
    engine = BacklinkEngine(notebookpath=notebookpath)
    engine.catch_up()

    event_handler = MarkdownHandler(engine)
    observer = PollingObserver(timeout=5) if use_polling else Observer()
    observer.schedule(event_handler, notebookpath, recursive=True)

    print(f"Monitoring {notebookpath}...")
    observer.start()

    print(f"Serving backlinks on {host}:{port}...")
    handler_class = backlink_handler_factory(engine=engine)
    server = HTTPServer((host, port), handler_class)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
        observer.stop()

    observer.join()


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--notebookpath")
    parser.add_argument("--polling", action="store_true")
    parser.add_argument("--port", default=5001, type=int)
    args = parser.parse_args()
    notebookpath = Path(args.notebookpath).resolve()

    host = '127.0.0.1'
    main(notebookpath=notebookpath, host=host, port=args.port, use_polling=args.polling)


