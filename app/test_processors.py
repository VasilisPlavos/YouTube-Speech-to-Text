import unittest
import os
import tempfile
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


if __name__ == '__main__':
    unittest.main()