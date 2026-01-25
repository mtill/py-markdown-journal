#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
import json
from pathlib import Path
import sqlite3
from noteslib import parseEntries, MARKDOWN_SUFFIX, LINK_REGEX, TAG_NAMESPACE_SEPARATOR
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote


DB_VERSION = "1_1"
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

        lt = lt.replace("/", TAG_NAMESPACE_SEPARATOR)


        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT source FROM backlinks 
                WHERE target = ?""", (lt, ))

            results = [row[0] for row in cursor.fetchall()]

        return sorted(results)

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
                             (abs_path, link))

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
        def do_GET(self):
            # unquote() handles URL-encoded characters like %20 for spaces
            # lstrip('/') removes the leading slash to get the filename
            target_path = unquote(self.path).lstrip('/')

            if not target_path:
                self.send_error(400, "Bad Request: Please provide a path (e.g., /file.md)")
                return

            response = engine.get_backlinks(target_path)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()

            self.wfile.write(json.dumps(response).encode('utf-8'))

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


