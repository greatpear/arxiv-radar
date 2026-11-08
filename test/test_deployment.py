"""Regression checks for the deployed SMTP and category configuration."""
import unittest
from unittest.mock import MagicMock, patch

import main
from src.construct_email import send_email


class MailTransportTests(unittest.TestCase):
    def test_port_465_uses_implicit_tls_without_plaintext_connection(self):
        with patch('src.construct_email.smtplib.SMTP') as plain, patch(
            'src.construct_email.smtplib.SMTP_SSL'
        ) as secure:
            send_email('sender@example.com', 'reader@example.com', 'test-code',
                       'smtp.example.com', 465, '<p>Daily papers</p>')
            self.assertEqual(plain.call_count, 0,
                             'Port 465 must begin with a TLS handshake')
            secure.assert_called_once()

    def test_port_587_upgrades_to_tls_before_authentication(self):
        with patch('src.construct_email.smtplib.SMTP') as plain, patch(
            'src.construct_email.smtplib.SMTP_SSL'
        ) as secure:
            send_email('sender@example.com', 'reader@example.com', 'test-code',
                       'smtp.example.com', 587, '<p>Daily papers</p>')
            connection = plain.return_value.__enter__.return_value
            methods = [call[0] for call in connection.method_calls]
            self.assertIn('starttls', methods)
            self.assertIn('login', methods)
            self.assertLess(methods.index('starttls'), methods.index('login'))
            self.assertEqual(secure.call_count, 0)


class RetrievalTests(unittest.TestCase):
    def test_debug_retrieval_respects_configured_categories(self):
        client = MagicMock()
        client.results.return_value = iter(())
        feed = MagicMock()
        feed.feed.title = 'Test arXiv feed'
        with patch('main.arxiv.Client', return_value=client), patch(
            'main.feedparser.parse', return_value=feed
        ):
            self.assertEqual(main.get_arxiv_paper('cs.IT+physics.optics', debug=True), [])
        query = client.results.call_args.args[0]
        self.assertEqual(query.query, 'cat:cs.IT OR cat:physics.optics')
        self.assertEqual(query.max_results, 5)


if __name__ == '__main__':
    unittest.main()
