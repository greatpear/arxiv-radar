"""Conservative publication matching and an auditable venue allowlist."""
import re
import time
import unicodedata

import requests


class PublicationLookupError(RuntimeError):
    """Publication data could not be checked; the run must be retried."""


# CAS large-category zones shown by LetPub, 2025-03 upgraded edition.
# This intentionally covers only checked venues, not every qualifying journal.
_JOURNALS = (
    ('IEEE Transactions on Wireless Communications', ('1536-1276', '1558-2248'), 1, 3428),
    ('IEEE Transactions on Communications', ('0090-6778', '1558-0857'), 2, 3372),
    ('IEEE Transactions on Cognitive Communications and Networking', ('2332-7731', '2372-2045'), 1, 10916),
    ('IEEE Transactions on Image Processing', ('1057-7149', '1941-0042'), 1, 3390),
    ('IEEE Internet of Things Journal', ('2327-4662', '2372-2541'), 2, 10193),
    ('IEEE Transactions on Circuits and Systems for Video Technology', ('1051-8215', '1558-2205'), 1, 3369),
    ('IEEE Transactions on Multimedia', ('1520-9210', '1941-0077'), 1, 3404),
    ('IEEE Transactions on Pattern Analysis and Machine Intelligence', ('0162-8828', '2160-9292', '1939-3539'), 1, 3411),
    ('IEEE Journal on Selected Areas in Communications', ('0733-8716', '1558-0008'), 1, 3340),
    ('IEEE Transactions on Mobile Computing', ('1536-1233', '1558-0660', '2161-9875'), 1, 3403),
    ('IEEE Transactions on Signal Processing', ('1053-587X', '1941-0476'), 2, 3419),
)
JOURNALS = {issn: (name, zone, journal_id)
            for name, identifiers, zone, journal_id in _JOURNALS for issn in identifiers}

_CONFERENCES = (
    ('CVPR', r'\bconference on computer vision and pattern recognition\b|\bcvpr\b', 'https://cvpr.thecvf.com/'),
    ('ICCV', r'\binternational conference on computer vision\b|\biccv\b', 'https://iccv.thecvf.com/'),
    ('NeurIPS', r'\badvances in neural information processing systems\b|\bneurips\b', 'https://neurips.cc/'),
    ('ICML', r'\binternational conference on machine learning\b|\bicml\b', 'https://icml.cc/'),
    ('ICLR', r'\binternational conference on learning representations\b|\biclr\b', 'https://iclr.cc/'),
    ('ACM MM', r'\bacm international conference on multimedia\b|\bacm multimedia\b', 'https://sigmm.org/'),
)
_WORKSHOP = re.compile(r'\b(?:workshops?|tutorials?|companion|supplement|demo|doctoral|symposium)\b', re.I)
_OTHER_CONFERENCES = re.compile(
    r'\binternational conference on machine learning\s+(?:and|&|for|in)\b|'
    r'\bacm (?:international conference on )?multimedia\s+(?:retrieval|systems|modeling|modelling)\b', re.I)


def _normalize(value):
    text = unicodedata.normalize('NFKD', value or '').casefold()
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return ' '.join(re.findall(r'[a-z0-9]+', text))


def _first_author_matches(paper, item):
    authors = getattr(paper, 'authors', None) or []
    candidates = item.get('author') or []
    if not authors or not candidates:
        return False
    name = _normalize(getattr(authors[0], 'name', str(authors[0])))
    family = _normalize(candidates[0].get('family', ''))
    given = _normalize(candidates[0].get('given', ''))
    if not name or not family or not given:
        return False
    words = name.split()
    family_words = family.split()
    if len(words) <= len(family_words) or words[-len(family_words):] != family_words:
        return False
    return words[0][0] == given[0]


def _lookup_crossref(title):
    last_error = None
    for attempt in range(3):
        try:
            response = requests.get(
                'https://api.crossref.org/works',
                params={'query.bibliographic': title, 'rows': 8}, timeout=25,
                headers={'User-Agent': 'arxiv-radar/1.0 (academic literature monitor)'},
            )
            response.raise_for_status()
            return response.json()['message']['items']
        except (requests.RequestException, ValueError, KeyError, TypeError) as error:
            last_error = error
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise PublicationLookupError(f'Crossref lookup failed: {last_error}') from last_error


def find_publication(paper, lookup=None):
    """Return evidence only for a title/first-author match in an allowed venue."""
    try:
        candidates = (lookup or _lookup_crossref)(paper.title)
    except Exception as error:
        if isinstance(error, PublicationLookupError):
            raise
        raise PublicationLookupError(f'Publication lookup failed: {error}') from error
    wanted = _normalize(paper.title)
    for item in candidates:
        titles = item.get('title') or []
        actual = _normalize(titles[0] if titles else '')
        if not actual or actual != wanted:
            continue
        if not _first_author_matches(paper, item):
            continue
        doi = item.get('DOI') or ''
        if not re.fullmatch(r'10\.\d{4,9}/\S+', doi, re.I):
            continue
        evidence = {'doi_url': 'https://doi.org/' + doi, 'metadata_source': 'Crossref'}
        if item.get('type') == 'journal-article':
            names = {_normalize(name) for name in item.get('container-title') or []}
            matches = [JOURNALS[issn.upper()] for issn in item.get('ISSN', [])
                       if issn.upper() in JOURNALS and _normalize(JOURNALS[issn.upper()][0]) in names]
            if matches:
                name, zone, journal_id = matches[0]
                evidence.update(name=name, rank=f'中科院大类{zone}区',
                                rank_version='2025年3月升级版',
                                rank_source=f'https://www.letpub.com.cn/index.php?journalid={journal_id}&page=journalapp&view=detail')
                return evidence
        if item.get('type') == 'proceedings-article':
            venue = ' '.join(item.get('container-title') or [])
            if _WORKSHOP.search(venue) or _OTHER_CONFERENCES.search(venue):
                continue
            for name, pattern, homepage in _CONFERENCES:
                if re.search(pattern, venue, re.I):
                    evidence.update(name=name, rank='顶级会议', rank_version='主会论文',
                                    rank_source=homepage)
                    return evidence
    return None
