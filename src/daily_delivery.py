"""Send a prepared daily digest at 10:00 Beijing time, with a persisted receipt."""
import argparse
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import time


BEIJING = timezone(timedelta(hours=8), 'Asia/Shanghai')
DEFAULT_RECEIPT = '.github/daily-delivery.json'


def beijing_now():
    return datetime.now(BEIJING)


def needs_delivery(receipt_path, moment):
    receipt_path = Path(receipt_path)
    if not receipt_path.exists():
        return True
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    receipt_date = date.fromisoformat(receipt['date'])
    if receipt.get('status') not in ('sent', 'empty_skipped'):
        raise ValueError('Daily delivery receipt has an invalid status')
    return receipt_date != moment.astimezone(BEIJING).date()


def write_receipt(receipt_path, moment, status):
    moment = moment.astimezone(BEIJING)
    receipt = {'date': moment.date().isoformat(), 'status': status,
               'completed_at': moment.isoformat(timespec='seconds'),
               'run_id': os.environ.get('GITHUB_RUN_ID')}
    receipt_path = Path(receipt_path)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    temporary.replace(receipt_path)


def deliver_digest(html_path, receipt_path, *, settings=None, clock=beijing_now,
                   sleeper=time.sleep, transport=None):
    if not needs_delivery(receipt_path, clock()):
        return False
    settings = os.environ if settings is None else settings
    html_path = Path(html_path)
    html = html_path.read_text(encoding='utf-8')
    report = json.loads(html_path.with_suffix('.json').read_text(encoding='utf-8'))
    send_empty = settings.get('SEND_EMPTY', '').lower() in ('true', '1')
    if not report['papers'] and not send_empty:
        write_receipt(receipt_path, clock(), 'empty_skipped')
        return False
    required = ('SENDER', 'RECEIVER', 'SENDER_PASSWORD', 'SMTP_SERVER')
    if any(not settings.get(name) for name in required):
        raise ValueError('Daily delivery SMTP configuration is incomplete')
    port = int(settings.get('SMTP_PORT') or 465)
    target = clock().astimezone(BEIJING).replace(hour=10, minute=0, second=0, microsecond=0)
    while (remaining := (target - clock().astimezone(BEIJING)).total_seconds()) > 0:
        sleeper(min(remaining, 60))
    if not needs_delivery(receipt_path, clock()):
        return False
    if transport is None:
        # The early gate must run using only the runner's standard library.
        from .construct_email import send_email
        transport = send_email
    transport(settings['SENDER'], settings['RECEIVER'], settings['SENDER_PASSWORD'],
              settings['SMTP_SERVER'], port, html)
    write_receipt(receipt_path, clock(), 'sent')
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('check', 'send'))
    parser.add_argument('--receipt', default=DEFAULT_RECEIPT)
    parser.add_argument('--html', default='output/daily.html')
    args = parser.parse_args()
    if args.action == 'check':
        needed = needs_delivery(args.receipt, beijing_now())
        result = f'should_send={str(needed).lower()}\n'
        print(result.strip(), flush=True)
        if output := os.environ.get('GITHUB_OUTPUT'):
            with open(output, 'a', encoding='utf-8') as handle:
                handle.write(result)
    else:
        sent = deliver_digest(args.html, args.receipt)
        print('Daily email accepted by SMTP' if sent else 'Daily delivery already complete or empty notice disabled',
              flush=True)


if __name__ == '__main__':
    main()
