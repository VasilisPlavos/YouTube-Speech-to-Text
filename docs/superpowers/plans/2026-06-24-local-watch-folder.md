# Local Watch-Folder Transcription Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a background watch-folder pipeline that auto-transcribes audio/video files dropped into `in/` to `.md`, then moves the original + `.md` to `out/` (or `error/` on failure), running alongside the existing YouTube HTTP endpoint in the same container.

**Architecture:** A daemon thread started at FastAPI startup polls `WATCH_DIR/in/` every few seconds. Stable files are normalized to WAV with `ffmpeg`, transcribed with the existing Whisper `get_text`, written to Markdown, and moved to `out/`. Each file is processed inside a unique `.work/<id>/` directory that is always deleted in a `finally` block. All transcription/IO logic lives in `processors.py`; the loop and dispatch live in a new `watcher.py`; `main.py` only wires the startup hook.

**Tech Stack:** Python 3, FastAPI (lifespan), `ffmpeg` (already in the image), `SpeechRecognition[whisper-local]`, stdlib `threading`/`shutil`/`subprocess`.

## Global Constraints

- **Docker-only for running the app.** Unit tests (`python -m unittest`) do **not** launch the app and may run on the host. Confirm before any non-Docker run of the app itself.
- **Run all tests from the `app/` directory** — modules import each other by bare name (`from processors import *`).
- If transcription deps aren't installed on the host, run the same test command inside the container:
  `docker run --rm -v "${PWD}/app:/app" -w /app youtube-to-text:latest python -m unittest <target>`
- **All file writes use `encoding="utf-8"`** — transcripts may be Greek/non-ASCII.
- **Sequential** processing, one file at a time. **No** retry on failure. **No** parallelism.
- **Reuse** the existing `get_text`. Do **not** change the behavior of `GET /` or `GET /yt/{id}`.
- Env defaults: `WATCH_DIR=/data`, `POLL_INTERVAL=5`, `DEFAULT_LANG` empty ⇒ Whisper auto-detect.
- Supported extensions (case-insensitive): audio `.mp3 .wav .m4a .flac .ogg .aac .opus .wma`; video `.mp4 .mkv .mov .avi .webm .flv`.

## File Structure

- `app/processors.py` (modify) — add pure helpers + ffmpeg/transcription orchestration: `is_supported_media`, `build_markdown`, `free_base`, `extract_audio_to_wav`, `transcribe_local_file`.
- `app/watcher.py` (create) — config constants, `find_stable_files`, `process_file`, `ensure_dirs`, `clean_work_dir`, `run_once`, `run_watch_loop`, `start_watcher`.
- `app/main.py` (modify) — FastAPI `lifespan` that calls `start_watcher()` on startup.
- `app/test_processors.py` (modify) — tests for the new processors helpers.
- `app/test_watcher.py` (create) — tests for the watcher module.
- `Dockerfile` / `README.md` (modify) — document the `-v` mount and env vars.

---

### Task 1: Pure media helpers in `processors.py`

**Files:**
- Modify: `app/processors.py`
- Test: `app/test_processors.py`

**Interfaces:**
- Consumes: nothing (uses stdlib `os` already imported in `processors.py`).
- Produces:
  - `SUPPORTED_EXTS: set[str]` (lowercase, dot-prefixed)
  - `is_supported_media(filename: str) -> bool`
  - `build_markdown(stem: str, text: str) -> str`
  - `free_base(target_dir: str, base: str, companion_exts: list[str]) -> str`

- [ ] **Step 1: Write the failing tests**

Append to `app/test_processors.py`:

```python
import os
import tempfile
from processors import is_supported_media, build_markdown, free_base


class TestIsSupportedMedia(unittest.TestCase):
    def test_audio_and_video_accepted_case_insensitive(self):
        for name in ["a.mp3", "b.WAV", "c.Mp4", "d.mkv", "e.opus"]:
            self.assertTrue(is_supported_media(name), name)

    def test_other_extensions_rejected(self):
        for name in ["a.txt", "b.md", "c", "d.json", "e.pdf"]:
            self.assertFalse(is_supported_media(name), name)


class TestBuildMarkdown(unittest.TestCase):
    def test_frontmatter_and_body(self):
        md = build_markdown("my song", "γεια σου κόσμε")
        self.assertEqual(
            md,
            "---\nchannel: local folder\nid: my song\n---\nγεια σου κόσμε\n",
        )


class TestFreeBase(unittest.TestCase):
    def test_no_collision_returns_base(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(free_base(d, "song", [".mp3", ".md"]), "song")

    def test_collision_appends_suffix(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "song.md"), "w").close()
            self.assertEqual(free_base(d, "song", [".mp3", ".md"]), "song-1")

    def test_multiple_collisions_increment(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, "song.md"), "w").close()
            open(os.path.join(d, "song-1.mp3"), "w").close()
            self.assertEqual(free_base(d, "song", [".mp3", ".md"]), "song-2")
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `app/`): `python -m unittest test_processors -v`
Expected: FAIL/ERROR — `ImportError: cannot import name 'is_supported_media'`.

- [ ] **Step 3: Write minimal implementation**

Append to `app/processors.py` (after the existing imports):

```python
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".opus", ".wma"}
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv"}
SUPPORTED_EXTS = AUDIO_EXTS | VIDEO_EXTS


def is_supported_media(filename):
    return os.path.splitext(filename)[1].lower() in SUPPORTED_EXTS


def build_markdown(stem, text):
    return f"---\nchannel: local folder\nid: {stem}\n---\n{text}\n"


def free_base(target_dir, base, companion_exts):
    candidate = base
    n = 0
    while any(os.path.exists(os.path.join(target_dir, candidate + e)) for e in companion_exts):
        n += 1
        candidate = f"{base}-{n}"
    return candidate
```

- [ ] **Step 4: Run tests to verify they pass**

Run (from `app/`): `python -m unittest test_processors -v`
Expected: PASS (all tests, including the existing `TestGetYoutubeId`).

- [ ] **Step 5: Commit**

```bash
git add app/processors.py app/test_processors.py
git commit -m "feat: add media-extension, markdown, and collision helpers"
```

---

### Task 2: ffmpeg extraction + local transcription orchestration

**Files:**
- Modify: `app/processors.py`
- Test: `app/test_processors.py`

**Interfaces:**
- Consumes: existing `get_text(audioFile, language=None) -> str`; stdlib `subprocess`, `os` (already imported).
- Produces:
  - `extract_audio_to_wav(input_path: str, workdir: str) -> str` (returns `<workdir>/audio.wav`)
  - `transcribe_local_file(input_path: str, workdir: str, language: str | None = None) -> str`

- [ ] **Step 1: Write the failing tests**

Append to `app/test_processors.py`:

```python
import processors


class TestExtractAudioToWav(unittest.TestCase):
    def test_builds_ffmpeg_command_and_returns_wav_path(self):
        captured = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            captured["kwargs"] = kwargs

        original = processors.subprocess.run
        processors.subprocess.run = fake_run
        try:
            with tempfile.TemporaryDirectory() as work:
                wav = processors.extract_audio_to_wav("/in/clip.mp4", work)
                self.assertEqual(wav, os.path.join(work, "audio.wav"))
                self.assertEqual(captured["cmd"][0], "ffmpeg")
                self.assertIn("/in/clip.mp4", captured["cmd"])
                self.assertIn("16000", captured["cmd"])
                self.assertIn(wav, captured["cmd"])
                self.assertTrue(captured["kwargs"].get("check"))
        finally:
            processors.subprocess.run = original


class TestTranscribeLocalFile(unittest.TestCase):
    def test_extracts_then_transcribes(self):
        calls = {}

        def fake_extract(input_path, workdir):
            calls["extract"] = (input_path, workdir)
            return os.path.join(workdir, "audio.wav")

        def fake_get_text(audioFile, language=None):
            calls["get_text"] = (audioFile, language)
            return "hello world"

        orig_extract = processors.extract_audio_to_wav
        orig_get_text = processors.get_text
        processors.extract_audio_to_wav = fake_extract
        processors.get_text = fake_get_text
        try:
            text = processors.transcribe_local_file("/in/clip.mp4", "/work", "en")
            self.assertEqual(text, "hello world")
            self.assertEqual(calls["extract"], ("/in/clip.mp4", "/work"))
            self.assertEqual(calls["get_text"], ("/work/audio.wav", "en"))
        finally:
            processors.extract_audio_to_wav = orig_extract
            processors.get_text = orig_get_text
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `app/`): `python -m unittest test_processors -v`
Expected: FAIL/ERROR — `AttributeError: module 'processors' has no attribute 'extract_audio_to_wav'`.

- [ ] **Step 3: Write minimal implementation**

Append to `app/processors.py`:

```python
def extract_audio_to_wav(input_path, workdir):
    wav_path = os.path.join(workdir, "audio.wav")
    cmd = ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", wav_path]
    subprocess.run(cmd, check=True)
    return wav_path


def transcribe_local_file(input_path, workdir, language=None):
    wav_path = extract_audio_to_wav(input_path, workdir)
    return get_text(wav_path, language)
```

- [ ] **Step 4: Run tests to verify they pass**

Run (from `app/`): `python -m unittest test_processors -v`
Expected: PASS.

> Note: `transcribe_local_file` calls module-level `extract_audio_to_wav`/`get_text`; the test patches `processors.<name>`, which the test relies on. Keep these as bare module-level calls (not aliased) so patching works.

- [ ] **Step 5: Commit**

```bash
git add app/processors.py app/test_processors.py
git commit -m "feat: add ffmpeg wav extraction and local-file transcription"
```

---

### Task 3: Watcher config + stable-file scan

**Files:**
- Create: `app/watcher.py`
- Test: `app/test_watcher.py`

**Interfaces:**
- Consumes: `is_supported_media` (Task 1) via `from processors import *`.
- Produces:
  - Module constants `WATCH_DIR`, `POLL_INTERVAL`, `DEFAULT_LANG`, `WORK_SUBDIR`.
  - `find_stable_files(in_dir: str, previous_sizes: dict) -> tuple[list[str], dict]`

- [ ] **Step 1: Write the failing tests**

Create `app/test_watcher.py`:

```python
import os
import tempfile
import unittest

import watcher


def _write(path, content=b"x"):
    with open(path, "wb") as f:
        f.write(content)


class TestFindStableFiles(unittest.TestCase):
    def test_new_file_not_ready_then_ready_when_stable(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "a.mp3"), b"1234")
            ready, sizes = watcher.find_stable_files(d, {})
            self.assertEqual(ready, [])
            self.assertEqual(sizes[os.path.join(d, "a.mp3")], 4)

            ready2, sizes2 = watcher.find_stable_files(d, sizes)
            self.assertEqual(ready2, [os.path.join(d, "a.mp3")])

    def test_growing_file_not_ready(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.mp3")
            _write(p, b"12")
            _, sizes = watcher.find_stable_files(d, {})
            _write(p, b"123456")  # grew between scans
            ready, _ = watcher.find_stable_files(d, sizes)
            self.assertEqual(ready, [])

    def test_ignores_unsupported_and_subdirs(self):
        with tempfile.TemporaryDirectory() as d:
            _write(os.path.join(d, "note.txt"), b"hi")
            os.mkdir(os.path.join(d, "sub"))
            ready, sizes = watcher.find_stable_files(d, {})
            self.assertEqual(ready, [])
            self.assertEqual(sizes, {})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `app/`): `python -m unittest test_watcher -v`
Expected: FAIL/ERROR — `ModuleNotFoundError: No module named 'watcher'`.

- [ ] **Step 3: Write minimal implementation**

Create `app/watcher.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run (from `app/`): `python -m unittest test_watcher -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/watcher.py app/test_watcher.py
git commit -m "feat: add watcher config and stable-file scan"
```

---

### Task 4: Per-file pipeline with guaranteed cleanup

**Files:**
- Modify: `app/watcher.py`
- Test: `app/test_watcher.py`

**Interfaces:**
- Consumes: `transcribe_local_file` (Task 2), `build_markdown`/`free_base` (Task 1), `WORK_SUBDIR` (Task 3).
- Produces: `process_file(base_dir: str, input_path: str, language: str | None, counter: int) -> None`

Behavior: build `out/<base>.md` + move original to `out/<base>.<ext>` on success; on any exception move original to `error/<base>.<ext>` and write `error/<base>.error.log`; always `rmtree` the per-file work dir.

- [ ] **Step 1: Write the failing tests**

Append to `app/test_watcher.py` (above the `if __name__` guard):

```python
import shutil as _shutil


class ProcessFileBase(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        for sub in ("in", "out", "error", watcher.WORK_SUBDIR):
            os.makedirs(os.path.join(self.base, sub))
        self.in_file = os.path.join(self.base, "in", "song.mp3")
        _write(self.in_file, b"audio-bytes")
        self._orig = watcher.transcribe_local_file

    def tearDown(self):
        watcher.transcribe_local_file = self._orig
        _shutil.rmtree(self.base, ignore_errors=True)


class TestProcessFileSuccess(ProcessFileBase):
    def test_moves_original_and_writes_md_and_cleans_work(self):
        watcher.transcribe_local_file = lambda p, w, language=None: "γεια"
        watcher.process_file(self.base, self.in_file, None, 1)

        out = os.path.join(self.base, "out")
        self.assertTrue(os.path.exists(os.path.join(out, "song.mp3")))
        with open(os.path.join(out, "song.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "---\nchannel: local folder\nid: song\n---\nγεια\n")
        self.assertFalse(os.path.exists(self.in_file))
        self.assertEqual(os.listdir(os.path.join(self.base, watcher.WORK_SUBDIR)), [])


class TestProcessFileError(ProcessFileBase):
    def test_moves_original_to_error_with_log_and_cleans_work(self):
        def boom(p, w, language=None):
            raise RuntimeError("ffmpeg exploded")

        watcher.transcribe_local_file = boom
        watcher.process_file(self.base, self.in_file, None, 1)

        err = os.path.join(self.base, "error")
        self.assertTrue(os.path.exists(os.path.join(err, "song.mp3")))
        with open(os.path.join(err, "song.error.log"), encoding="utf-8") as f:
            self.assertIn("ffmpeg exploded", f.read())
        self.assertFalse(os.path.exists(self.in_file))
        self.assertEqual(os.listdir(os.path.join(self.base, watcher.WORK_SUBDIR)), [])


class TestProcessFileCollision(ProcessFileBase):
    def test_suffixes_when_output_exists(self):
        open(os.path.join(self.base, "out", "song.md"), "w").close()
        watcher.transcribe_local_file = lambda p, w, language=None: "hi"
        watcher.process_file(self.base, self.in_file, None, 1)

        out = os.path.join(self.base, "out")
        self.assertTrue(os.path.exists(os.path.join(out, "song-1.mp3")))
        self.assertTrue(os.path.exists(os.path.join(out, "song-1.md")))
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `app/`): `python -m unittest test_watcher -v`
Expected: FAIL/ERROR — `AttributeError: module 'watcher' has no attribute 'process_file'`.

- [ ] **Step 3: Write minimal implementation**

Append to `app/watcher.py`:

```python
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
        shutil.move(input_path, os.path.join(err_dir, final_base + ext))
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run (from `app/`): `python -m unittest test_watcher -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/watcher.py app/test_watcher.py
git commit -m "feat: add per-file transcription pipeline with guaranteed cleanup"
```

---

### Task 5: Directory setup, single pass, loop, and watcher startup

**Files:**
- Modify: `app/watcher.py`
- Test: `app/test_watcher.py`

**Interfaces:**
- Consumes: `find_stable_files` (Task 3), `process_file` (Task 4), config constants (Task 3).
- Produces:
  - `ensure_dirs(base_dir: str) -> None`
  - `clean_work_dir(base_dir: str) -> None`
  - `run_once(base_dir: str, sizes: dict, counter: int, language) -> tuple[dict, int]`
  - `run_watch_loop(base_dir: str, poll_interval: int, language) -> None` (infinite; not unit-tested)
  - `start_watcher() -> threading.Thread`

- [ ] **Step 1: Write the failing tests**

Append to `app/test_watcher.py` (above the `if __name__` guard):

```python
class TestEnsureAndCleanDirs(unittest.TestCase):
    def test_ensure_dirs_creates_all(self):
        with tempfile.TemporaryDirectory() as d:
            watcher.ensure_dirs(d)
            for sub in ("in", "out", "error", watcher.WORK_SUBDIR):
                self.assertTrue(os.path.isdir(os.path.join(d, sub)), sub)

    def test_clean_work_dir_empties_but_recreates(self):
        with tempfile.TemporaryDirectory() as d:
            work = os.path.join(d, watcher.WORK_SUBDIR)
            os.makedirs(os.path.join(work, "orphan-1"))
            watcher.clean_work_dir(d)
            self.assertTrue(os.path.isdir(work))
            self.assertEqual(os.listdir(work), [])


class TestRunOnce(ProcessFileBase):
    def test_processes_only_stable_files(self):
        watcher.transcribe_local_file = lambda p, w, language=None: "hi"
        in_dir = os.path.join(self.base, "in")
        # First pass: file seen but not yet stable -> nothing processed.
        sizes, counter = watcher.run_once(self.base, {}, 0, None)
        self.assertTrue(os.path.exists(self.in_file))
        self.assertEqual(counter, 0)
        # Second pass: stable -> processed and moved out.
        sizes, counter = watcher.run_once(self.base, sizes, counter, None)
        self.assertFalse(os.path.exists(self.in_file))
        self.assertEqual(counter, 1)
        self.assertTrue(os.path.exists(os.path.join(self.base, "out", "song.md")))


class TestStartWatcher(unittest.TestCase):
    def test_starts_daemon_thread_with_config(self):
        recorded = {}
        orig = watcher.run_watch_loop

        def fake_loop(base, interval, lang):
            recorded["args"] = (base, interval, lang)

        watcher.run_watch_loop = fake_loop
        try:
            t = watcher.start_watcher()
            t.join(timeout=2)
            self.assertTrue(t.daemon)
            self.assertEqual(recorded["args"][0], watcher.WATCH_DIR)
            self.assertEqual(recorded["args"][1], watcher.POLL_INTERVAL)
        finally:
            watcher.run_watch_loop = orig
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `app/`): `python -m unittest test_watcher -v`
Expected: FAIL/ERROR — `AttributeError: module 'watcher' has no attribute 'ensure_dirs'`.

- [ ] **Step 3: Write minimal implementation**

Append to `app/watcher.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run (from `app/`): `python -m unittest test_watcher -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/watcher.py app/test_watcher.py
git commit -m "feat: add dir setup, scan/process pass, watch loop, and startup"
```

---

### Task 6: Wire watcher into FastAPI startup + document the mount

**Files:**
- Modify: `app/main.py`
- Test: `app/test_watcher.py`
- Modify: `Dockerfile`, `README.md`

**Interfaces:**
- Consumes: `start_watcher` (Task 5).
- Produces: `main.lifespan` (async context manager) that calls `start_watcher()` once on startup; `main.app` keeps the existing routes.

- [ ] **Step 1: Write the failing test**

Append to `app/test_watcher.py` (above the `if __name__` guard):

```python
import asyncio


class TestMainLifespanStartsWatcher(unittest.TestCase):
    def test_lifespan_calls_start_watcher(self):
        import main

        called = []
        orig = main.start_watcher
        main.start_watcher = lambda: called.append(True)

        async def run():
            async with main.lifespan(main.app):
                pass

        try:
            asyncio.run(run())
        finally:
            main.start_watcher = orig
        self.assertEqual(called, [True])
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `app/`): `python -m unittest test_watcher.TestMainLifespanStartsWatcher -v`
Expected: FAIL/ERROR — `AttributeError: module 'main' has no attribute 'lifespan'`.

- [ ] **Step 3: Implement the wiring**

Edit `app/main.py`. Replace the top section (imports + `app = FastAPI()`) with:

```python
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import BackgroundTasks, FastAPI, Query
from fastapi.responses import RedirectResponse
from processors import *
from watcher import start_watcher

# cmd: fastapi dev


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_watcher()
    yield


app = FastAPI(lifespan=lifespan)
```

Leave the two route handlers (`read_root`, `yt_id`) exactly as they are.

- [ ] **Step 4: Run the test (and full suite) to verify it passes**

Run (from `app/`): `python -m unittest test_watcher test_processors -v`
Expected: PASS for all tests.

- [ ] **Step 5: Document the mount in `Dockerfile` and `README.md`**

In `Dockerfile`, update the run-comment block at the bottom to include the volume mount and env vars:

```dockerfile
# docker build -t youtube-to-text:latest .
# docker run -d --name youtube-to-text -p 3300:80 -v /host/media:/data youtube-to-text:latest
# Drop audio/video files into /host/media/in ; transcripts appear in /host/media/out
# Optional env: -e POLL_INTERVAL=5 -e DEFAULT_LANG=en -e WATCH_DIR=/data
# YouTube endpoint still available at http://localhost:3300/yt/swXWUfufu2w
```

In `README.md`, add a short "Local watch-folder" section describing: mount one folder at `/data`, drop files into `in/`, transcripts + originals land in `out/`, failures land in `error/`, and the `POLL_INTERVAL`/`DEFAULT_LANG`/`WATCH_DIR` env vars.

- [ ] **Step 6: Commit**

```bash
git add app/main.py app/test_watcher.py Dockerfile README.md
git commit -m "feat: start watch-folder on app startup and document the mount"
```

---

### Task 7: End-to-end verification via Docker

**Files:** none (verification only).

This is the only step that runs the app; per the project rule it runs **via Docker**.

- [ ] **Step 1: Build the image**

```bash
docker build -t youtube-to-text:latest .
```
Expected: build succeeds.

- [ ] **Step 2: Run with a mounted folder**

```bash
mkdir -p /tmp/media/in
docker run -d --name ytt -p 3300:80 -v /tmp/media:/data youtube-to-text:latest
```
Expected: container starts; `/tmp/media/in`, `out`, `error` exist (created on startup).

- [ ] **Step 3: Drop a short audio/video file and observe**

Copy a small `.mp3`/`.mp4` into `/tmp/media/in/`. Within `POLL_INTERVAL`×2 seconds plus transcription time:
- Expected: the original moves to `/tmp/media/out/<name>.<ext>` and `/tmp/media/out/<name>.md` is created with the `channel: local folder` frontmatter and a transcript body.
- Check logs: `docker logs ytt`.

- [ ] **Step 4: Confirm the YouTube endpoint still works**

```bash
curl -s http://localhost:3300/yt/swXWUfufu2w
```
Expected: a JSON status response (existing behavior unchanged).

- [ ] **Step 5: Tear down**

```bash
docker rm -f ytt
```

---

## Self-Review

**Spec coverage:**
- Mounted folder + `in/`/`out/`/`error/` layout → Tasks 5 (`ensure_dirs`), 6, 7.
- Polling detection + stability check → Task 3.
- Supported audio/video formats → Task 1.
- ffmpeg→WAV→Whisper pipeline → Tasks 2, 4.
- Markdown frontmatter (`channel: local folder`, `id`, body) → Tasks 1, 4.
- Move original + `.md` to `out/` → Task 4.
- Per-process unique work dir + `finally` cleanup → Task 4.
- Collision suffixing → Tasks 1, 4.
- Error → `error/` + `.error.log`, no retry → Task 4.
- Startup `.work/` cleanup → Task 5 (`clean_work_dir`).
- Code structure (`watcher.py` / `processors.py` / thin `main.py`) → Tasks 2–6.
- Config env vars → Task 3.
- Coexistence with YouTube endpoint unchanged → Task 6 + Task 7 step 4.
- Tests without real Whisper/ffmpeg → Tasks 1–6 (all transcription monkeypatched).

No gaps found.

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step contains complete code.

**Type consistency:** `find_stable_files` returns `(ready, sizes)` and `run_once` consumes/returns `(sizes, counter)` consistently; `process_file(base_dir, input_path, language, counter)` signature matches all call sites; `transcribe_local_file(input_path, workdir, language=None)` matches Task 2 definition and Task 4/5 monkeypatches; `free_base(target_dir, base, companion_exts)` consistent across Tasks 1 and 4; `build_markdown(stem, text)` output string identical in Tasks 1 and 4.
