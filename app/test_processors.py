import unittest
import os
import json
import tempfile
import processors
from processors import get_youtube_id, is_supported_media, build_markdown, free_base

class TestGetYoutubeId(unittest.TestCase):

    def test_valid_url(self):
        url = 'http://youtu.be/SA2iWivDJiE'
        self.assertEqual(get_youtube_id(url), 'SA2iWivDJiE')

    def test_invalid_urls(self):

        invalid_urls = [
            'invalid-url',
            '',
            None
            ]
        
        for url in invalid_urls:
            self.assertEqual(get_youtube_id(url), '')

    def test_non_string_input_returns_empty(self):
        for value in [123, 3.14, [], {}, object()]:
            self.assertEqual(get_youtube_id(value), '')

    def test_different_types_of_urls(self):

        valid_urls = [
            'http://youtu.be/SA2iWivDJiE',
            'http://www.youtube.com/watch?v=_oPAwA_Udwc&feature=feedu',
            'http://www.youtube.com/embed/SA2iWivDJiE',
            'http://www.youtube.com/v/SA2iWivDJiE?version=3&amp;hl=en_US',
            'https://www.youtube.com/watch?v=rTHlyTphWP0&index=6&list=PLjeDyYvG6-40qawYNR4juzvSOg-ezZ2a6',
            'youtube.com/watch?v=_lOT2p_FCvA',
            'youtu.be/watch?v=_lOT2p_FCvA',
            'https://www.youtube.com/watch?time_continue=9&v=n0g-Y0oo5Qs&feature=emb_logo'
            ]

        for url in valid_urls:
            id = get_youtube_id(url)
            self.assertEqual(len(id), 11)


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


class TestRunProcessInBackground(unittest.TestCase):
    def test_unsupported_channel_returns_without_running_pipeline(self):
        called = {"get_audio": False}

        def boom(*args, **kwargs):
            called["get_audio"] = True
            raise AssertionError("get_audio must not run for an unsupported channel")

        original = processors.get_audio
        processors.get_audio = boom
        cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as d:
                os.chdir(d)
                processors.run_process_in_background("vimeo", "abc123def45")
                self.assertFalse(called["get_audio"])
                index_path = os.path.join(d, "vimeo", "abc123def45", "index.json")
                self.assertTrue(os.path.exists(index_path))
                with open(index_path) as f:
                    data = json.load(f)
                self.assertEqual(data["status"], "vimeo is not supported")
        finally:
            os.chdir(cwd)
            processors.get_audio = original


if __name__ == '__main__':
    unittest.main()