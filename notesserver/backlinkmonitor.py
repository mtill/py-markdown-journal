import time
import argparse
from pathlib import Path
import sqlite3
from noteslib import MARKDOWN_SUFFIX, LINK_REGEX
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler


class BacklinkEngine:
    def __init__(self, notebookpath):
        self.notebookpath = notebookpath
        self.db_path = notebookpath / ".backlinks.sqlite"
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

    def extract_links(self, file_path):
        links = set()
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"could not read {file_path}: {e}")

        for l in LINK_REGEX.findall(content):
            lt = l[1]
            if lt.startswith("/"):
                lt = lt[1:]
            lt = (notebookpath / lt).relative_to(notebookpath).as_posix()
            links.add(lt)

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


def main(notebookpath, use_polling=False):
    engine = BacklinkEngine(notebookpath=notebookpath)

    engine.catch_up()

    event_handler = MarkdownHandler(engine)
    observer = PollingObserver(timeout=2) if use_polling else Observer()
    observer.schedule(event_handler, notebookpath, recursive=True)
    
    print(f"Monitoring {notebookpath}...")
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--notebookpath")
    parser.add_argument("--polling", action="store_true")
    args = parser.parse_args()
    notebookpath = Path(args.notebookpath).resolve()

    main(notebookpath=notebookpath, use_polling=args.polling)

