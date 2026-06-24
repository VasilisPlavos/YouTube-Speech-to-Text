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
