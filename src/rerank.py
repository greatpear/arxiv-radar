import json
import math
import re
import time
from typing import List

from loguru import logger

from .llm import set_global_llm
from .paper import ArxivPaper
from .relevance import is_target_communication, is_thesis_relevant


def rerank_paper(papers: List[ArxivPaper], retriever_target: str,
                 model: str = 'bartowski/Llama-3.2-3B-Instruct-GGUF',
                 model_url: str = 'Llama-3.2-3B-Instruct-Q4_K_M.gguf',
                 min_score: float = 70) -> List[ArxivPaper]:
    """Filter by communication topic, score, then rank eligible papers."""
    if not 0 < min_score <= 100:
        raise ValueError('min_score must be greater than zero and at most 100')
    interests = [item.strip() for item in (retriever_target or '').splitlines() if item.strip()]
    candidates = [paper for paper in papers if is_thesis_relevant(paper)]
    logger.info(f'Thesis topic filter: {len(candidates)}/{len(papers)} candidates')
    if not candidates or not interests:
        return []
    set_global_llm(model=model, model_path=model_url)
    accepted = []
    for index, paper in enumerate(candidates, 1):
        logger.info(f'Scoring {index}/{len(candidates)}: {paper.title}')
        try:
            score = calculate_paper_score(paper, interests)
            valid = type(score) in (int, float) and math.isfinite(score) and min_score <= score <= 100
            paper.score = float(score) if valid else 0.0
            if valid:
                accepted.append(paper)
            logger.info(f'Score: {paper.score}; accepted: {valid}')
        except Exception as error:
            paper.score = 0.0
            logger.error(f'Could not score {paper.arxiv_id}: {error}')
        time.sleep(0.5)
    accepted.sort(key=lambda paper: (not bool(is_target_communication(paper)), -paper.score))
    logger.info(f'Relevance threshold {min_score}: {len(accepted)}/{len(candidates)} papers retained')
    return accepted


def truncate_interest(interest: str, max_length: int = 40) -> str:
    return interest if len(interest) <= max_length else interest[:max_length - 3] + '...'


def calculate_paper_score(paper: ArxivPaper, interests: List[str]) -> float:
    from .llm import get_llm

    paper.score = 0.0
    paper.interest_scores = {}
    paper.high_score_interests = []
    topics = {f'T{index}': interest for index, interest in enumerate(interests, 1)}
    if not topics:
        return 0.0
    zero_example = {key: 0 for key in topics}
    relevant_example = dict(zero_example)
    relevant_example['T1'] = 94
    prompt = f'''Evaluate this paper for a master's researcher studying IMAGE JSCC AND RECONSTRUCTION.
Prioritize explicit spatial/2D position or relative monocular depth priors, geometric or
spatial attention, structure preservation and channel/SNR-adaptive visual JSCC.
Relevant baselines include SwinJSCC, FAJSCC, MambaJSCC and ResiComp-style packet-loss
resilient learned visual coding. Visual geometry/attention papers without communication
may qualify as auxiliary methods if their mechanism could transfer to image reconstruction.
Underwater acoustic, optical and mixed channels are optional application settings.
Speech-only, text-only and unrelated communication/networking papers should score below 70.
Do not treat network depth or antenna spatial dimensions as image depth/geometry.
Topics (IDs must stay unchanged): {json.dumps(topics)}

Score each topic from 0 to 100 based on the main technical contribution:
90-100: directly solves a problem in that communication topic.
70-89: substantial contribution to visual communication or transferable visual geometry methods.
1-69: peripheral connection or a passing mention; not suitable for recommendation.
0: unrelated.
Optical materials, photon emitters, quantum gauge fields, boson sampling,
and generic information-bottleneck theory must score 0 unless the paper evaluates
an actual data-bearing communication system in one of the listed topics.
The word "optical", "acoustic", "semantic" or "information" alone does not establish relevance.
Ordinary optical links, ISAC sensing, underwater equalization/channel estimation,
and unrelated uses of Mamba/Transformers must score 0.
Do not give a paper a high score solely for its physical carrier, environment,
or for citing the exemplars. Evaluate the actual communication method.

For example, a paper that directly solves only topic T1: {json.dumps(relevant_example)}
Unrelated material-emission or quantum-physics paper: {json.dumps(zero_example)}

Paper title: {paper.title}
Paper abstract: {paper.summary[:3000]}

Return ONLY one JSON object with exactly these keys: {json.dumps(list(topics))}.
Use integer scores. Include all topic IDs. Do not split or rename topics. No explanation.'''
    try:
        response = get_llm().generate([
            {'role': 'system', 'content': 'Evaluate communication-system paper relevance. Return only the requested JSON.'},
            {'role': 'user', 'content': prompt},
        ])
        match = re.search(r'\{.*\}', response, re.DOTALL)
        scores = json.loads(match.group()) if match else None
        if not isinstance(scores, dict) or set(scores) != set(topics):
            raise ValueError('Model response did not preserve the configured topic IDs')
        if any(type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100
               for value in scores.values()):
            raise ValueError('Model response contained an invalid relevance score')
        paper.interest_scores = {topics[key]: value for key, value in scores.items()}
        paper.high_score_interests = [interest for interest, score in paper.interest_scores.items() if score >= 80]
        paper.score = float(max(scores.values()))
    except Exception as error:
        logger.warning(f'Relevance scoring rejected for {paper.arxiv_id}: {error}')
    return paper.score
