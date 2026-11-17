"""Publication identity and venue-quality checks for daily recommendations."""
import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

if importlib.util.find_spec('src.publication'):
    from src.publication import find_publication, PublicationLookupError
else:
    find_publication = None
    PublicationLookupError = Exception


TITLE = 'Deep Joint Source-Channel Coding for Wireless Image Transmission'


def paper(title=TITLE, author='Deniz Gunduz'):
    return SimpleNamespace(title=title, authors=[SimpleNamespace(name=author)])


def record(**overrides):
    result = {
        'title': [TITLE], 'author': [{'given': 'Deniz', 'family': 'Gunduz'}],
        'type': 'journal-article', 'ISSN': ['1536-1276'],
        'container-title': ['IEEE Transactions on Wireless Communications'],
        'DOI': '10.1109/TWC.2026.1234567',
    }
    result.update(overrides)
    return result


class PublicationFilterTests(unittest.TestCase):
    def test_publication_filter_is_available(self):
        self.assertIsNotNone(find_publication, 'Publication verification is not implemented')

    def find(self, item, papers=None):
        return find_publication(paper() if item is None else item,
                                lookup=lambda title: papers if papers is not None else [record()])

    def test_matching_journal_is_accepted_with_quartile_and_evidence(self):
        if find_publication is None:
            self.skipTest('Publication verification not implemented')
        evidence = self.find(None)
        self.assertEqual(evidence['name'], 'IEEE Transactions on Wireless Communications')
        self.assertEqual(evidence['rank'], '中科院大类1区')
        self.assertIn('2025', evidence['rank_version'])
        self.assertTrue(evidence['doi_url'].startswith('https://doi.org/'))
        self.assertIn('letpub.com.cn', evidence['rank_source'])

    def test_preprint_unknown_journal_wrong_title_or_author_are_not_accepted(self):
        if find_publication is None:
            self.skipTest('Publication verification not implemented')
        for item in [record(type='posted-content'), record(ISSN=['9999-9999']),
                     record(title=['A different publication']),
                     record(author=[{'given': 'Other', 'family': 'Person'}]),
                     record(**{'container-title': ['A different journal']}),
                     record(DOI=None)]:
            with self.subTest(item=item):
                self.assertIsNone(self.find(None, [item]))

    def test_main_conference_is_accepted_but_workshops_are_not(self):
        if find_publication is None:
            self.skipTest('Publication verification not implemented')
        conference = record(type='proceedings-article', ISSN=[],
                            **{'container-title': ['2025 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)']})
        evidence = self.find(None, [conference])
        self.assertEqual(evidence['name'], 'CVPR')
        conference['container-title'] = ['2025 IEEE/CVF CVPR Workshops']
        self.assertIsNone(self.find(None, [conference]))

    def test_similarly_named_conference_is_not_treated_as_a_top_venue(self):
        conference = record(type='proceedings-article', ISSN=[],
                            **{'container-title': ['2025 International Conference on Machine Learning and Computing']})
        self.assertIsNone(self.find(None, [conference]))
        conference['container-title'] = ['ACM International Conference on Multimedia Retrieval']
        self.assertIsNone(self.find(None, [conference]))

    def test_lookup_errors_are_not_treated_as_no_matching_publications(self):
        if find_publication is None:
            self.skipTest('Publication verification not implemented')
        def fail(_title):
            raise OSError('service unreachable')
        with self.assertRaises(PublicationLookupError):
            find_publication(paper(), lookup=fail)

    def test_crossref_candidates_must_match_title_and_first_author(self):
        if find_publication is None:
            self.skipTest('Publication verification not implemented')
        unrelated = record(title=['Deep Joint Source-Channel Coding for Video'])
        wrong_author = record(author=[{'family': 'Someone'}])
        self.assertIsNone(self.find(None, [unrelated, wrong_author]))

    def test_nearby_but_different_title_does_not_borrow_venue_status(self):
        self.assertIsNone(self.find(None, [record(title=[TITLE + ' II'])]))

    def test_first_author_requires_full_family_name_and_given_initial(self):
        self.assertIsNone(self.find(paper(author='Alice Johnson'),
                                    [record(author=[{'given': 'Alice', 'family': 'Son'}])]))


class PipelineQualityTests(unittest.TestCase):
    def test_rendered_email_includes_publication_and_ranking_sources(self):
        from src.construct_email import get_block_html
        evidence = {'name': 'Journal', 'rank': '中科院大类1区', 'rank_version': '2025',
                    'rank_source': 'https://example.org/rank', 'doi_url': 'https://doi.org/10.1109/test'}
        html = get_block_html('Paper', 'Author', '', 90, '2601.00001', '摘要',
                              'https://arxiv.org/pdf/2601.00001', publication=evidence)
        for text in ('Journal', '中科院大类1区', 'https://doi.org/10.1109/test', 'https://example.org/rank'):
            self.assertIn(text, html)

    def test_quality_gate_runs_before_scoring_and_keeps_evidence(self):
        import main
        self.assertTrue(hasattr(main, 'find_publication'), 'Pipeline does not check publication quality')
        accepted = paper(); rejected = paper('An unverified preprint')
        accepted.arxiv_id = '2601.00001'; accepted.pdf_url = 'https://arxiv.org/pdf/2601.00001'
        rejected.arxiv_id = '2601.00002'
        accepted.score = 92; accepted.interest_scores = {}; accepted.tldr = '中文摘要'
        evidence = {'name': 'A verified venue', 'rank': '中科院大类1区',
                    'rank_version': '2025', 'rank_source': 'https://example.org/rank',
                    'doi_url': 'https://doi.org/10.1109/test'}
        with TemporaryDirectory() as folder:
            args = SimpleNamespace(arxiv_query='cs.IT', debug=False, topic_query='', min_score=70,
                retriever_target='image JSCC', max_paper_num=20, use_llm_api=False, language='Chinese',
                dry_run=True, output=str(Path(folder) / 'daily.html'), send_empty=True)
            with patch('main.get_arxiv_paper', return_value=[accepted, rejected]), \
                 patch('main.find_publication', side_effect=[evidence, None]), \
                 patch('main.load_pending_publications', return_value={}), \
                 patch('main.load_recommended_ids', return_value=set()), \
                 patch('main.rerank_paper', return_value=[accepted]) as rank, \
                 patch('main.set_global_llm'), patch('main.destroy_global_llm'), \
                 patch('main.render_email', return_value='digest'):
                report = main.run_radar(args)
            self.assertEqual(rank.call_args.args[0], [accepted])
            self.assertEqual(report['papers'][0]['publication'], evidence)
            self.assertEqual(json.loads(Path(args.output).with_suffix('.json').read_text(encoding='utf-8'))['papers'][0]['publication'], evidence)


if __name__ == '__main__':
    unittest.main()
