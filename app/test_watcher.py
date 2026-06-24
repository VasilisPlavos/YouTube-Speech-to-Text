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
