import os
import tempfile
import unittest
import shutil as _shutil

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


if __name__ == "__main__":
    unittest.main()
