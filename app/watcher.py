import os
import time
import shutil
import threading
import traceback
from processors import *

WATCH_DIR = os.environ.get("WATCH_DIR", "/data")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))
DEFAULT_LANG = os.environ.get("DEFAULT_LANG") or None
WORK_SUBDIR = ".work"


def find_stable_files(in_dir, previous_sizes):
    current_sizes = {}
    ready = []
    for name in sorted(os.listdir(in_dir)):
        path = os.path.join(in_dir, name)
        if not os.path.isfile(path):
            continue
        if not is_supported_media(name):
            continue
        size = os.path.getsize(path)
        current_sizes[path] = size
        if previous_sizes.get(path) == size:
            ready.append(path)
    return ready, current_sizes


def process_file(base_dir, input_path, language, counter):
    name = os.path.basename(input_path)
    stem, ext = os.path.splitext(name)
    work_dir = os.path.join(base_dir, WORK_SUBDIR, f"{stem}-{counter}")
    os.makedirs(work_dir, exist_ok=True)
    try:
        text = transcribe_local_file(input_path, work_dir, language)
        md = build_markdown(stem, text)
        out_dir = os.path.join(base_dir, "out")
        os.makedirs(out_dir, exist_ok=True)
        final_base = free_base(out_dir, stem, [ext, ".md"])
        md_tmp = os.path.join(work_dir, "transcript.md")
        with open(md_tmp, "w", encoding="utf-8") as f:
            f.write(md)
        shutil.move(md_tmp, os.path.join(out_dir, final_base + ".md"))
        shutil.move(input_path, os.path.join(out_dir, final_base + ext))
    except Exception:
        err_dir = os.path.join(base_dir, "error")
        os.makedirs(err_dir, exist_ok=True)
        final_base = free_base(err_dir, stem, [ext, ".error.log"])
        with open(os.path.join(err_dir, final_base + ".error.log"), "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        if os.path.exists(input_path):
            shutil.move(input_path, os.path.join(err_dir, final_base + ext))
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def ensure_dirs(base_dir):
    for sub in ("in", "out", "error", WORK_SUBDIR):
        os.makedirs(os.path.join(base_dir, sub), exist_ok=True)


def clean_work_dir(base_dir):
    work_root = os.path.join(base_dir, WORK_SUBDIR)
    shutil.rmtree(work_root, ignore_errors=True)
    os.makedirs(work_root, exist_ok=True)


def run_once(base_dir, sizes, counter, language):
    in_dir = os.path.join(base_dir, "in")
    ready, sizes = find_stable_files(in_dir, sizes)
    for path in ready:
        counter += 1
        process_file(base_dir, path, language, counter)
    return sizes, counter


def run_watch_loop(base_dir, poll_interval, language):
    ensure_dirs(base_dir)
    clean_work_dir(base_dir)
    sizes = {}
    counter = 0
    while True:
        sizes, counter = run_once(base_dir, sizes, counter, language)
        time.sleep(poll_interval)


def start_watcher():
    t = threading.Thread(
        target=run_watch_loop,
        args=(WATCH_DIR, POLL_INTERVAL, DEFAULT_LANG),
        daemon=True,
    )
    t.start()
    return t
