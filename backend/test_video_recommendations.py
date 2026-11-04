"""Restoring a chat keeps eligible public links and their honest labels."""
import unittest
from backend.services.youtube import restore_recommendations


class SavedVideoTests(unittest.TestCase):
    def video(self, identity='abcdefghijk', channel='channel'):
        return dict(title='Related tutorial', url=f'https://www.youtube.com/watch?v={identity}',
                    channel_id=channel, timestamp=None, matched_using='title_and_description')

    def test_approved_channel_link_survives_general_chat_restore(self):
        links = restore_recommendations([self.video()], {'video_ids': None}, {'channel'})
        self.assertEqual(len(links), 1)
        self.assertFalse(links[0]['content_verified'])
        self.assertIn('not been verified', links[0]['notice'])

    def test_removed_channel_and_disabled_video_scope_drop_the_link(self):
        self.assertEqual(restore_recommendations([self.video()], {'video_ids': None}, set()), [])
        self.assertEqual(restore_recommendations([self.video()], {'video_ids': []}, {'channel'}), [])

    def test_only_currently_published_guide_links_are_restored(self):
        link = self.video(channel='')
        scope = {'video_ids': None, 'guide_video_ids': ['abcdefghijk']}
        self.assertEqual(len(restore_recommendations([link], scope, set())), 1)
        self.assertEqual(restore_recommendations([link], {'video_ids': None}, set()), [])

    def test_explicit_scope_allows_its_video_only(self):
        links = restore_recommendations([self.video(), self.video('lmnopqrstuv')],
                                        {'video_ids': ['lmnopqrstuv']}, set())
        self.assertEqual([v['url'] for v in links], ['https://www.youtube.com/watch?v=lmnopqrstuv'])

    def test_invalid_urls_and_duplicate_links_are_removed(self):
        link = self.video()
        bad = [{**link, 'url': 'https://evil.example/watch?v=abcdefghijk'},
               {**link, 'url': 'https://www.youtube.com@evil.example/watch?v=abcdefghijk'},
               {**link, 'url': 'https://www.youtube.com/watch?v=bad-id'},
               {**link, 'url': 'javascript:alert(1)'}]
        links = restore_recommendations(bad + [link, link], {'video_ids': None}, {'channel'})
        self.assertEqual(len(links), 1)


if __name__ == '__main__':
    unittest.main()
