"""Regression checks for the deployed SMTP and category configuration."""
import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import main
from src.construct_email import send_email
from src.rerank import calculate_paper_score, rerank_paper


def sample_paper(title, summary, score=0):
    return SimpleNamespace(
        title=title, summary=summary, score=score, arxiv_id='test-paper',
        interest_scores={}, high_score_interests=[], tldr='测试中文摘要',
        pdf_url='https://arxiv.org/pdf/test-paper',
    )


COMMUNICATION_PAPERS = [
    ('Deep Joint Source-Channel Coding for Wireless Image Transmission',
     'We design a DeepJSCC encoder and decoder for semantic communication over fading channels.'),
    ('Feature Importance-Aware Deep Joint Source-Channel Coding for Computationally Efficient and Adjustable Image Transmission',
     'FAJSCC uses selective deformable self-attention and independently adjustable encoder and decoder complexity.'),
    ('MambaJSCC: Adaptive Deep Joint Source-Channel Coding with Generalized State Space Model',
     'A visual state space model transmits images with CSI adaptation and low computational overhead.'),
    ('ResiComp: Loss-Resilient Image Compression via Dual-Functional Masked Visual Token Modeling',
     'A neural image codec jointly optimizes compression efficiency and packet loss concealment using masked visual tokens.'),
    ('Cross-Modal Semantic Successive Refinement for Generative Image Communication over Underwater Acoustic Channels',
     'A generative semantic codec reliably reconstructs images over bandwidth-limited underwater acoustic channels.'),
    ('Adaptive DeepJSCC for Underwater Wireless Optical Image Transmission',
     'A neural image encoder and decoder jointly adapt to the SNR of underwater optical channels.'),
    ('Hybrid Acoustic-Optical Underwater Video Transmission with a Learned Erasure-Resilient Codec',
     'A learned video codec handles packet erasures across hybrid underwater acoustic and optical links.'),
    ('Improved Nonlinear Transform Source-Channel Coding to Catalyze Semantic Communications',
     'NTSCC learns semantic latent features and an entropy model for variable-rate JSCC over wireless channels.'),
]

IRRELEVANT_PAPERS = [
    ('Room-Temperature Quantum Emission from Boron Nitride Nanotubes',
     'We study single-photon emission in nanotubes and their integration into nanophotonic devices.'),
    ('Dynamical effects induced by synthetic SU(1,1) gauge fields',
     'Non-Abelian gauge fields cause wave packet and entanglement dynamics in spinor condensates.'),
    ('Polynomial-time classical simulation of boson and fermion sampling under thermal loss',
     'We present a classical algorithm for noisy boson and fermion sampling.'),
    ('Deep-learning surrogate model for rapid quantum-noise computation in dual-pump fiber-optic phase-sensitive amplifiers',
     'A surrogate model accelerates quantum-noise computations for phase-sensitive amplifiers.'),
    ('Dynamics Aware Past-Future Information Bottleneck',
     'We use block Hankel matrices and Lie groups to realize dynamic systems for estimation and control.'),
    ('Sensing-Based Communication: A Non-Orthogonal Passive Reflection Framework for ISAC',
     'An optical retro-reflective system unifies reflective sensing and uplink communication using OOK tags and SIC decoding.'),
    ('Adaptive Equalization for Underwater Acoustic Communications',
     'We evaluate an underwater acoustic communication link using OFDM and bit error rate.'),
    ('Channel Modeling for Underwater Wireless Optical Links',
     'We model the channel impulse response, scattering and turbulence of an underwater optical link.'),
    ('LLM-Based Text Semantic Communications',
     'Language models transmit sentences over noisy wireless channels for text semantic communication.'),
    ('Mamba for Medical Image Segmentation',
     'A visual state space network segments medical images with low computational complexity.'),
    ('High-Performance Learned Image Compression',
     'A neural image codec improves rate-distortion performance using a Transformer entropy model.'),
]


class RecommendationTests(unittest.TestCase):
    def rank_without_loading_models(self, papers):
        with patch('src.rerank.set_global_llm'), patch(
            'src.rerank.calculate_paper_score', side_effect=lambda paper, interests: paper.score
        ), patch('src.rerank.time.sleep'):
            return rerank_paper(papers, 'Semantic communications\nUnderwater acoustic communications')

    def test_zero_score_papers_are_removed_instead_of_filling_the_email(self):
        relevant = sample_paper(*COMMUNICATION_PAPERS[0], score=93)
        irrelevant = sample_paper(*IRRELEVANT_PAPERS[0], score=0)
        self.assertEqual(self.rank_without_loading_models([irrelevant, relevant]), [relevant])

    def test_materials_and_quantum_physics_do_not_pass_even_with_a_bad_model_score(self):
        papers = [sample_paper(title, abstract, score=95) for title, abstract in IRRELEVANT_PAPERS]
        self.assertEqual(self.rank_without_loading_models(papers), [])

    def test_requested_communication_topics_survive_the_domain_filter(self):
        papers = [sample_paper(title, abstract, score=91) for title, abstract in COMMUNICATION_PAPERS]
        self.assertEqual(self.rank_without_loading_models(papers), papers)

    def test_threshold_is_applied_before_limiting_recommendations(self):
        papers = [sample_paper(*COMMUNICATION_PAPERS[0], score=score) for score in (0, 69, 70, 92)]
        self.assertEqual(self.rank_without_loading_models(papers), [papers[3], papers[2]])


class SemanticScoreTests(unittest.TestCase):
    def score_response(self, response):
        paper = sample_paper(*COMMUNICATION_PAPERS[0])
        llm = MagicMock()
        llm.generate.return_value = response
        with patch('src.llm.get_llm', return_value=llm):
            score = calculate_paper_score(paper, ['Semantic communications', 'Underwater acoustic communications'])
        return score, paper

    def test_topic_ids_are_mapped_back_to_the_configured_interests(self):
        score, paper = self.score_response('{"T1": 94, "T2": 12}')
        self.assertEqual(score, 94)
        self.assertEqual(paper.interest_scores, {'Semantic communications': 94, 'Underwater acoustic communications': 12})
        self.assertEqual(paper.high_score_interests, ['Semantic communications'])

    def test_invented_or_missing_topics_cannot_create_a_recommendation(self):
        for response in ('{"Optical materials": 99}', '{"T1": 99}', '{"T1": 90, "T2": 0, "T3": 99}'):
            with self.subTest(response=response):
                score, paper = self.score_response(response)
                self.assertEqual(score, 0)
                self.assertEqual(paper.high_score_interests, [])

    def test_invalid_scores_are_rejected(self):
        for value in ('101', '-2', 'NaN', 'true', '"99"'):
            with self.subTest(value=value):
                score, _ = self.score_response('{"T1": ' + value + ', "T2": 0}')
                self.assertEqual(score, 0)


class DeliveryPipelineTests(unittest.TestCase):
    def arguments(self, output, **overrides):
        values = dict(
            arxiv_query='cs.IT+eess.SP', debug=True, topic_query='"semantic communication"',
            min_score=70, retriever_target='Semantic communications', max_paper_num=20,
            use_llm_api=False, openai_api_key=None, openai_api_base=None, model_name=None,
            language='Chinese', dry_run=True, output=str(output), send_empty=True,
            sender='sender@example.com', receiver='reader@example.com',
            sender_password='test-code', smtp_server='smtp.example.com', smtp_port=465,
        )
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_preview_writes_the_actual_selection_without_sending(self):
        paper = sample_paper(*COMMUNICATION_PAPERS[0], score=93)
        with TemporaryDirectory() as folder:
            output = Path(folder) / 'preview.html'
            with patch('main.get_arxiv_paper', return_value=[paper]), patch(
                'main.rerank_paper', return_value=[paper]
            ), patch('main.set_global_llm'), patch('main.destroy_global_llm'), patch(
                'main.render_email', return_value='<p>Semantic communication: 93</p>'
            ), patch('main.send_email') as send:
                main.run_radar(self.arguments(output))
            self.assertFalse(send.called)
            report = json.loads(output.with_suffix('.json').read_text(encoding='utf-8'))
            self.assertEqual(report['papers'][0]['title'], COMMUNICATION_PAPERS[0][0])
            self.assertEqual(report['papers'][0]['score'], 93)
            self.assertIn('Semantic communication', output.read_text(encoding='utf-8'))

    def test_all_rejected_papers_produce_an_empty_notice_without_summary_inference(self):
        paper = sample_paper(*IRRELEVANT_PAPERS[0])
        with TemporaryDirectory() as folder:
            with patch('main.get_arxiv_paper', return_value=[paper]), patch(
                'main.rerank_paper', return_value=[]
            ), patch('main.set_global_llm') as initialize, patch(
                'main.destroy_global_llm'
            ), patch('main.send_email') as send:
                report = main.run_radar(self.arguments(Path(folder) / 'empty.html', dry_run=False))
            self.assertEqual(report['papers'], [])
            self.assertFalse(initialize.called)
            self.assertEqual(send.call_count, 1)
            self.assertNotIn(IRRELEVANT_PAPERS[0][0], send.call_args.args[-1])


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
    def test_daily_feed_filters_before_metadata_requests_and_keeps_resilient_visual_codecs(self):
        relevant = SimpleNamespace(
            id='oai:arXiv.org:2502.10812v1', arxiv_announce_type='new',
            title=COMMUNICATION_PAPERS[3][0], summary=COMMUNICATION_PAPERS[3][1],
        )
        unrelated = SimpleNamespace(
            id='oai:arXiv.org:2611.08809v1', arxiv_announce_type='new',
            title=IRRELEVANT_PAPERS[5][0], summary=IRRELEVANT_PAPERS[5][1],
        )
        client = MagicMock()
        client.results.return_value = iter([relevant])
        feed = SimpleNamespace(feed=SimpleNamespace(title='arXiv feed'), entries=[unrelated, relevant])
        with patch('main.arxiv.Client', return_value=client), patch('main.feedparser.parse', return_value=feed):
            papers = main.get_arxiv_paper('eess.IV+cs.IT')
        self.assertEqual(client.results.call_args.args[0].id_list, ['2502.10812v1'])
        self.assertEqual([paper.title for paper in papers], [COMMUNICATION_PAPERS[3][0]])

    def test_debug_search_uses_the_communication_topic_query(self):
        client = MagicMock()
        client.results.return_value = iter(())
        feed = MagicMock()
        feed.feed.title = 'Test arXiv feed'
        with patch('main.arxiv.Client', return_value=client), patch(
            'main.feedparser.parse', return_value=feed
        ):
            main.get_arxiv_paper('cs.IT+eess.SP', debug=True,
                                 topic_query='"semantic communication" OR "underwater acoustic communication"')
        query = client.results.call_args.args[0]
        self.assertIn('cat:cs.IT OR cat:eess.SP', query.query)
        self.assertIn('AND ("semantic communication" OR "underwater acoustic communication")', query.query)

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
