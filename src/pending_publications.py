"""Track recent relevant preprints until their publication can be verified."""
from datetime import date
import json
from pathlib import Path


DEFAULT_PENDING = '.github/pending-publications.json'
MAX_AGE_DAYS = 730
RECHECKS_PER_DAY = 20


def load_pending_publications(path=DEFAULT_PENDING):
    path = Path(path)
    if not path.exists():
        return {}
    papers = json.loads(path.read_text(encoding='utf-8'))['papers']
    if not isinstance(papers, dict):
        raise ValueError('Pending publication ledger is invalid')
    for arxiv_id, record in papers.items():
        if not isinstance(arxiv_id, str) or not isinstance(record, dict):
            raise ValueError('Pending publication ledger is invalid')
        date.fromisoformat(record['first_seen'])
        date.fromisoformat(record['last_checked'])
    return papers


def write_pending_publications(path, papers):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'papers': papers}, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def active_pending(pending, sent_ids, today):
    return {arxiv_id: record for arxiv_id, record in pending.items()
            if arxiv_id not in sent_ids
            and (today - date.fromisoformat(record['first_seen'])).days <= MAX_AGE_DAYS}


def select_due(pending, today, limit=RECHECKS_PER_DAY):
    due = [(record['last_checked'], record['first_seen'], arxiv_id)
           for arxiv_id, record in pending.items()
           if date.fromisoformat(record['last_checked']) < today]
    return [item[2] for item in sorted(due)[:limit]]


def update_pending(pending, candidates, sent_ids, today, deferred_ids=()):
    result = active_pending(pending, sent_ids, today)
    for paper in candidates:
        arxiv_id = paper.arxiv_id
        if paper.publication is None or arxiv_id in deferred_ids:
            first_seen = result.get(arxiv_id, {}).get('first_seen', today.isoformat())
            result[arxiv_id] = {'first_seen': first_seen, 'last_checked': today.isoformat()}
        else:
            result.pop(arxiv_id, None)
    return result
