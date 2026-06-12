#!/usr/bin/env python3
"""
watch_manuscript.py — Manuscript Change Monitor Daemon
Watches the Manuscript Masters directory for edits to the Draft 6.7 DOCX file,
debounces the events (waiting for safe saves/syncs to finish),
and triggers the rebuild_and_deploy.sh script.
"""

import sys
import time
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Config
GDRIVE_DIR  = Path("/Users/gabrielmcp/Library/CloudStorage/GoogleDrive-gabemcpherson@gmail.com/My Drive/Manuscript Masters")
TARGET_FILE = GDRIVE_DIR / "String Theory - Draft 6.7.docx"
REPO_DIR    = GDRIVE_DIR / "string-theory-chapters"
RUN_SCRIPT  = REPO_DIR / "rebuild_and_deploy.sh"
DEBOUNCE_SEC = 5

class ManuscriptWatcherHandler(FileSystemEventHandler):
    def __init__(self, target_file, run_script, debounce_sec=5):
        self.target_file = Path(target_file).resolve()
        self.run_script = Path(run_script).resolve()
        self.debounce_sec = debounce_sec
        self.last_modified = 0
        self.triggered = False

    def process_event(self, path):
        try:
            resolved_path = Path(path).resolve()
            if resolved_path == self.target_file:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Detected change in target: {self.target_file.name}", flush=True)
                self.last_modified = time.time()
                self.triggered = True
        except Exception as e:
            # Handle temporary/unresolvable paths during safe saves
            if self.target_file.name in str(path):
                self.last_modified = time.time()
                self.triggered = True

    def on_modified(self, event):
        if not event.is_directory:
            self.process_event(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self.process_event(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self.process_event(event.dest_path)

    def check_trigger(self):
        if self.triggered and (time.time() - self.last_modified) >= self.debounce_sec:
            self.triggered = False
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Quiet period ended. Invoking build and deploy pipeline...", flush=True)
            try:
                # Launch the deploy script and print output
                proc = subprocess.run([str(self.run_script)], capture_output=True, text=True, check=True)
                print(proc.stdout, flush=True)
            except subprocess.CalledProcessError as e:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ERROR: Rebuild and deploy failed with exit code {e.returncode}.", file=sys.stderr, flush=True)
                print(e.stderr, file=sys.stderr, flush=True)
            except Exception as e:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ERROR running deploy script: {e}", file=sys.stderr, flush=True)

def main():
    print(f"=== Starting Manuscript Watcher Daemon ===", flush=True)
    print(f"Watching directory: {GDRIVE_DIR}", flush=True)
    print(f"Target file:        {TARGET_FILE.name}", flush=True)
    print(f"Deploy script:      {RUN_SCRIPT}", flush=True)
    
    if not TARGET_FILE.exists():
        print(f"WARNING: Target file {TARGET_FILE} does not exist yet. Will watch and wait.", flush=True)
        
    handler = ManuscriptWatcherHandler(TARGET_FILE, RUN_SCRIPT, DEBOUNCE_SEC)
    observer = Observer()
    observer.schedule(handler, path=str(GDRIVE_DIR), recursive=False)
    observer.start()
    
    print("Daemon active. Press Ctrl+C to stop.", flush=True)
    
    try:
        while True:
            handler.check_trigger()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping observer...", flush=True)
        observer.stop()
    observer.join()
    print("Watcher daemon stopped.", flush=True)

if __name__ == "__main__":
    main()
