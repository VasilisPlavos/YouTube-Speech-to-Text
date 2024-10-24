import unittest
from processors import get_youtube_id

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


if __name__ == '__main__':
    unittest.main()