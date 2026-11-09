"""Delivery timing, failed-send recovery, and duplicate prevention."""
import importlib.util
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


class Clock:
    def __init__(self, value):
        self.value = value
        self.waits = []

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.value += timedelta(seconds=seconds)


class DailyDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('src.daily_delivery'),
                             'Daily delivery timing and retry protection are missing')
        from src import daily_delivery
        self.delivery = daily_delivery
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.receipt = self.root / 'delivery.json'
        self.html = self.root / 'daily.html'
        self.html.write_text('<p>通信论文日报</p>', encoding='utf-8')
        self.html.with_suffix('.json').write_text(json.dumps({
            'candidate_count': 43, 'minimum_score': 70,
            'papers': [{'arxiv_id': '2611.08809', 'title': 'Optical communication'}],
        }), encoding='utf-8')
        self.settings = dict(SENDER='sender@example.com', RECEIVER='reader@example.com',
                             SENDER_PASSWORD='test-code', SMTP_SERVER='smtp.example.com',
                             SMTP_PORT='465', SEND_EMPTY='true')
        self.clock = Clock(datetime(2026, 11, 10, 1, 59, 30, tzinfo=timezone.utc))
        self.messages = []

    def deliver(self, transport=None):
        def capture(*args):
            self.assertFalse(self.receipt.exists(), 'A receipt must follow SMTP acceptance')
            self.messages.append((self.clock.value, args))
        return self.delivery.deliver_digest(
            self.html, self.receipt, settings=self.settings,
            clock=self.clock.now, sleeper=self.clock.sleep,
            transport=transport or capture,
        )

    def test_prepared_digest_waits_for_ten_oclock_beijing(self):
        self.assertTrue(self.deliver())
        self.assertEqual(self.messages[0][0], datetime(2026, 11, 10, 2, tzinfo=timezone.utc))
        self.assertEqual(self.clock.waits, [30])
        self.assertEqual(self.messages[0][1][-1], '<p>通信论文日报</p>')
        receipt = json.loads(self.receipt.read_text(encoding='utf-8'))
        self.assertEqual(receipt['date'], '2026-11-10')
        self.assertEqual(receipt['status'], 'sent')

    def test_delayed_run_sends_immediately(self):
        self.clock.value = datetime(2026, 11, 10, 2, 27, tzinfo=timezone.utc)
        self.assertTrue(self.deliver())
        self.assertEqual(self.clock.waits, [])

    def test_successful_delivery_prevents_the_backup_from_sending_again(self):
        self.deliver()
        self.assertFalse(self.deliver())
        self.assertEqual(len(self.messages), 1)

    def test_failed_smtp_send_remains_eligible_for_a_backup(self):
        def failure(*args):
            raise OSError('SMTP unavailable')
        with self.assertRaisesRegex(OSError, 'SMTP unavailable'):
            self.deliver(transport=failure)
        self.assertFalse(self.receipt.exists())
        self.assertTrue(self.delivery.needs_delivery(self.receipt, self.clock.now()))
        self.assertTrue(self.deliver())

    def test_beijing_calendar_day_controls_duplicate_detection(self):
        self.receipt.write_text('{"date":"2026-11-09","status":"sent"}', encoding='utf-8')
        before_midnight = datetime(2026, 11, 9, 15, 59, tzinfo=timezone.utc)
        after_midnight = datetime(2026, 11, 9, 16, 1, tzinfo=timezone.utc)
        self.assertFalse(self.delivery.needs_delivery(self.receipt, before_midnight))
        self.assertTrue(self.delivery.needs_delivery(self.receipt, after_midnight))

    def test_invalid_receipt_fails_visibly_instead_of_risking_duplicate_email(self):
        self.receipt.write_text('not json', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.delivery.needs_delivery(self.receipt, self.clock.now())

    def test_empty_notice_is_delivered_when_enabled(self):
        self.html.with_suffix('.json').write_text('{"papers":[]}', encoding='utf-8')
        self.assertTrue(self.deliver())
        self.assertEqual(len(self.messages), 1)

    def test_disabled_empty_notice_completes_the_day_without_email(self):
        self.html.with_suffix('.json').write_text('{"papers":[]}', encoding='utf-8')
        self.settings['SEND_EMPTY'] = 'false'
        self.assertFalse(self.deliver())
        self.assertEqual(self.messages, [])
        self.assertFalse(self.delivery.needs_delivery(self.receipt, self.clock.now()))

    def test_gate_runs_without_installed_dependencies_and_sets_github_output(self):
        local_today = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
        self.receipt.write_text(json.dumps({'date': local_today, 'status': 'sent'}), encoding='utf-8')
        output = self.root / 'github-output'
        result = subprocess.run(
            [sys.executable, '-S', '-m', 'src.daily_delivery', 'check',
             '--receipt', str(self.receipt)],
            cwd=Path(__file__).resolve().parents[1],
            env=dict(os.environ, GITHUB_OUTPUT=str(output)),
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('should_send=false', output.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
