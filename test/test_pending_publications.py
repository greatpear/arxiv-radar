"""Keep relevant preprints under observation after their first arXiv announcement."""
import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import main
from src.pending_publications import active_pending, select_due, update_pending


class PendingPublicationTests(unittest.TestCase):
    def test_eligible_preprint_is_rechecked_even_without_an_arxiv_update(self):
        entry = {'first_seen': '2026-10-01', 'last_checked': '2026-11-01'}
        pending = {'2610.00001': entry}
        feed = SimpleNamespace(feed=SimpleNamespace(title='arXiv feed'), entries=[])
        result = SimpleNamespace(title='Image DeepJSCC', summary='visual image communication')
        client = MagicMock()
        client.results.return_value = iter([result])
        with patch('main.arxiv.Client', return_value=client), \
             patch('main.feedparser.parse', return_value=feed), \
             patch('main.load_recommended_ids', return_value=set()), \
             patch('main.load_pending_publications', return_value=pending), \
             patch('main.beijing_now', return_value=datetime(2026, 11, 17, tzinfo=timezone.utc)):
            papers = main.get_arxiv_paper('cs.IT')
        self.assertEqual(client.results.call_args.args[0].id_list, ['2610.00001'])
        self.assertEqual(papers[0].title, result.title)

    def test_bounded_oldest_first_selection_and_expiry(self):
        today = date(2026, 11, 17)
        pending = {
            'older': {'first_seen': '2026-01-01', 'last_checked': '2026-10-01'},
            'newer': {'first_seen': '2026-01-01', 'last_checked': '2026-11-01'},
            'today': {'first_seen': '2026-11-17', 'last_checked': '2026-11-17'},
            'sent': {'first_seen': '2026-01-01', 'last_checked': '2026-01-01'},
            'expired': {'first_seen': '2024-01-01', 'last_checked': '2024-02-01'},
        }
        eligible = active_pending(pending, {'sent'}, today)
        self.assertEqual(select_due(eligible, today, limit=1), ['older'])
        self.assertEqual(select_due(eligible, today, limit=20), ['older', 'newer'])
        self.assertNotIn('expired', eligible)
        self.assertNotIn('sent', eligible)

    def test_unpublished_paper_stays_pending_until_venue_is_verified(self):
        today = date(2026, 11, 17)
        preprint = SimpleNamespace(arxiv_id='2611.00001', publication=None)
        pending = update_pending({}, [preprint], set(), today)
        self.assertEqual(pending['2611.00001'], {
            'first_seen': '2026-11-17', 'last_checked': '2026-11-17'})
        published = SimpleNamespace(arxiv_id=preprint.arxiv_id, publication={'name': 'CVPR'})
        self.assertEqual(update_pending(pending, [published], set(), date(2026, 11, 18)), {})

    def test_qualified_paper_deferred_by_daily_limit_stays_pending(self):
        item = SimpleNamespace(arxiv_id='2611.00001', publication={'name': 'CVPR'})
        pending = update_pending({}, [item], set(), date(2026, 11, 17), {item.arxiv_id})
        self.assertIn(item.arxiv_id, pending)


if __name__ == '__main__':
    unittest.main()
