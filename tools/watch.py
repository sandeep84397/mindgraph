"""Real-time file watcher daemon — auto-updates fingerprints on file changes."""
from __future__ import annotations
import argparse
import os
import signal
import sys
import threading
import time
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
except ImportError:
    Observer = None

from tools.db import get_connection, delete_sections_for_file
from tools.fingerprint import fingerprint_file
from tools.parser import parse_sections, compute_content_hash

SKIP_FILES = {"schema.md", "index.md", "log.md"}
DEBOUNCE_SECONDS = 2.0


class MindGraphHandler(FileSystemEventHandler):
    """Handles file system events with debouncing and queued processing."""

    def __init__(self, kb_root: Path, watch_dirs: list[Path]):
        self.kb_root = kb_root
        self.watch_dirs = watch_dirs
        self.pending: dict[str, float] = {}  # path → timestamp
        self.lock = threading.Lock()
        self.worker = threading.Thread(target=self._process_loop, daemon=True)
        self.running = True
        self.worker.start()

    def _should_handle(self, path: str) -> bool:
        """Check if this file should trigger an update."""
        p = Path(path)
        if p.name.startswith(".") or p.name in SKIP_FILES:
            return False
        if p.suffix not in (".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".go",
                            ".rs", ".java", ".c", ".cpp", ".h", ".rb", ".txt",
                            ".yaml", ".yml", ".json", ".toml", ".sh", ".swift",
                            ".kt", ".cs", ".markdown", ".rst"):
            return False
        return True

    def on_modified(self, event: FileSystemEvent):
        if event.is_directory or not self._should_handle(event.src_path):
            return
        with self.lock:
            self.pending[event.src_path] = time.time()

    def on_created(self, event: FileSystemEvent):
        if event.is_directory or not self._should_handle(event.src_path):
            return
        with self.lock:
            self.pending[event.src_path] = time.time()

    def on_deleted(self, event: FileSystemEvent):
        if event.is_directory:
            return
        filepath = Path(event.src_path)
        wiki_dir = self.kb_root / "wiki"
        try:
            rel_path = str(filepath.relative_to(self.kb_root))
            conn = get_connection(self.kb_root)
            removed = delete_sections_for_file(conn, rel_path)
            conn.close()
            if removed:
                _log(f"Deleted: {rel_path} ({removed} sections removed)")
        except (ValueError, Exception):
            pass

    def _process_loop(self):
        """Background worker: process debounced changes."""
        while self.running:
            time.sleep(0.5)
            now = time.time()
            ready = []

            with self.lock:
                for path, ts in list(self.pending.items()):
                    if now - ts >= DEBOUNCE_SECONDS:
                        ready.append(path)
                        del self.pending[path]

            for path in ready:
                self._process_change(Path(path))

    def _process_change(self, filepath: Path):
        """Process a single file change."""
        if not filepath.exists():
            return

        wiki_dir = self.kb_root / "wiki"
        conn = get_connection(self.kb_root)

        try:
            # If it's a wiki file, re-fingerprint it
            try:
                filepath.relative_to(wiki_dir)
                is_wiki_file = True
            except ValueError:
                is_wiki_file = False

            if is_wiki_file and filepath.suffix == ".md":
                stats = fingerprint_file(self.kb_root, filepath, conn)
                _log(f"Updated: {filepath.name} "
                     f"({stats['new']} new, {stats['updated']} updated, "
                     f"{stats['stale_removed']} stale)")
            else:
                # Non-wiki file: auto-create a wiki node if it doesn't exist
                from tools.auto_node import auto_create_node
                result = auto_create_node(filepath, self.kb_root)
                if result:
                    _log(f"Auto-created: wiki/{result['wiki_page']} "
                         f"({result['sections']} sections)")
        except Exception as e:
            _log(f"Error processing {filepath.name}: {e}")
        finally:
            conn.close()

    def stop(self):
        self.running = False
        self.worker.join(timeout=5)


def _log(message: str):
    """Print timestamped log message."""
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {message}", flush=True)


def get_pid_path(kb_root: Path) -> Path:
    return kb_root / ".mindgraph" / "watcher.pid"


def start_watcher(kb_root: Path, watch_dirs: list[Path] | None = None, foreground: bool = False):
    """Start the file watcher daemon."""
    if Observer is None:
        print("Error: watchdog not installed. Run: pip install watchdog")
        sys.exit(1)

    pid_path = get_pid_path(kb_root)
    if pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            os.kill(pid, 0)  # check if running
            print(f"Watcher already running (PID {pid})")
            return
        except (ProcessLookupError, ValueError):
            pid_path.unlink()

    if watch_dirs is None:
        watch_dirs = [kb_root / "wiki"]
        # Also watch project source dirs if they exist
        for d in ["src", "lib", "app", "pkg"]:
            if (kb_root / d).is_dir():
                watch_dirs.append(kb_root / d)

    handler = MindGraphHandler(kb_root, watch_dirs)
    observer = Observer()
    for d in watch_dirs:
        if d.exists():
            observer.schedule(handler, str(d), recursive=True)
            _log(f"Watching: {d}")

    observer.start()

    if not foreground:
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text(str(os.getpid()))

    def shutdown(sig, frame):
        _log("Stopping watcher...")
        handler.stop()
        observer.stop()
        observer.join(timeout=5)
        if pid_path.exists():
            pid_path.unlink()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    _log("MindGraph watcher started. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown(None, None)


def stop_watcher(kb_root: Path):
    """Stop the watcher daemon via PID file."""
    pid_path = get_pid_path(kb_root)
    if not pid_path.exists():
        print("No watcher running.")
        return

    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        print(f"Stopped watcher (PID {pid})")
    except ProcessLookupError:
        print("Watcher process not found (stale PID file)")
    except ValueError:
        print("Invalid PID file")
    finally:
        if pid_path.exists():
            pid_path.unlink()


def status_watcher(kb_root: Path):
    """Check if the watcher daemon is running."""
    pid_path = get_pid_path(kb_root)
    if not pid_path.exists():
        print("Watcher: not running")
        return

    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, 0)
        print(f"Watcher: running (PID {pid})")
    except ProcessLookupError:
        print("Watcher: not running (stale PID file)")
        pid_path.unlink()
    except ValueError:
        print("Watcher: invalid PID file")


def main():
    parser = argparse.ArgumentParser(description="MindGraph file watcher daemon")
    parser.add_argument("kb_root", help="Knowledge base root directory")
    parser.add_argument("action", choices=["start", "stop", "status"],
                        help="Daemon action")
    parser.add_argument("--foreground", action="store_true",
                        help="Run in foreground (don't write PID file)")
    parser.add_argument("--watch", nargs="+", help="Additional directories to watch")
    args = parser.parse_args()

    kb_root = Path(args.kb_root).resolve()

    if args.action == "start":
        extra_dirs = [Path(d).resolve() for d in args.watch] if args.watch else None
        start_watcher(kb_root, extra_dirs, args.foreground)
    elif args.action == "stop":
        stop_watcher(kb_root)
    elif args.action == "status":
        status_watcher(kb_root)


if __name__ == "__main__":
    main()
