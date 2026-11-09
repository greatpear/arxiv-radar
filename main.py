import arxiv
import argparse
import os
import feedparser
import sys
import json
from pathlib import Path
from tqdm import tqdm
from src.paper import ArxivPaper
from src.rerank import rerank_paper
from src.llm import destroy_global_llm, set_global_llm
from src.construct_email import render_email, send_email
from loguru import logger
from src.relevance import DEFAULT_TOPIC_QUERY, is_target_communication

# 配置日志
logger.remove()  # 移除默认的日志配置
logger.add(sys.stdout, level="INFO", format="{time} - {name} - {level} - {message}")

def get_arxiv_paper(query: str, debug: bool = False, topic_query: str = None) -> list[ArxivPaper]:
    client = arxiv.Client(num_retries=10, delay_seconds=10)
    feed = feedparser.parse(f"https://rss.arxiv.org/atom/{query}")
    if 'Feed error for query' in feed.feed.title:
        raise Exception(f"Invalid ARXIV_QUERY: {query}.")
    if not debug:
        papers = []
        new_entries = [item for item in feed.entries if item.arxiv_announce_type == 'new']
        all_paper_ids = [item.id.removeprefix("oai:arXiv.org:") for item in new_entries
                         if is_target_communication(item)]
        logger.info(f'New RSS entries: {len(new_entries)}; method-matched candidates: {len(all_paper_ids)}')
        bar = tqdm(total=len(all_paper_ids), desc="Retrieving Arxiv papers")
        for i in range(0, len(all_paper_ids),20):
            search = arxiv.Search(id_list=all_paper_ids[i:i+20])
            batch = [ArxivPaper(p) for p in client.results(search)]
            bar.update(len(batch))
            papers.extend(batch)
        bar.close()

    else:
        logger.debug("Retrieve 5 arxiv papers regardless of the date.")
        category_query = ' OR '.join(f'cat:{category.strip()}' for category in query.split('+') if category.strip())
        if topic_query:
            category_query = f'({category_query}) AND ({topic_query})'
        search = arxiv.Search(query=category_query, max_results=5, sort_by=arxiv.SortCriterion.SubmittedDate)
        papers = []
        for i in client.results(search):
            papers.append(ArxivPaper(i))
            if len(papers) == 5:
                break

    return papers


def run_radar(args):
    if not args.arxiv_query or not args.retriever_target:
        raise ValueError('ARXIV_QUERY and RETRIEVER_TARGET must be configured')
    if not 0 < args.min_score <= 100:
        raise ValueError('MIN_SCORE must be greater than zero and at most 100')
    if args.max_paper_num != -1 and args.max_paper_num < 1:
        raise ValueError('MAX_PAPER_NUM must be positive or -1')
    logger.info('Retrieving communication papers...')
    candidates = get_arxiv_paper(args.arxiv_query, args.debug, args.topic_query)
    papers = []
    if candidates:
        papers = rerank_paper(candidates, args.retriever_target, min_score=args.min_score)
        if args.max_paper_num != -1:
            papers = papers[:args.max_paper_num]
    destroy_global_llm()
    interests = [item.strip() for item in args.retriever_target.splitlines() if item.strip()]
    try:
        if papers:
            if args.use_llm_api:
                set_global_llm(api_key=args.openai_api_key, base_url=args.openai_api_base,
                               model=args.model_name, lang=args.language)
            else:
                set_global_llm(model='Qwen/Qwen2.5-3B-Instruct-GGUF',
                               model_path='qwen2.5-3b-instruct-q4_k_m.gguf', lang=args.language)
        html = render_email(papers, interests)
    finally:
        destroy_global_llm()
    report = {
        'candidate_count': len(candidates), 'minimum_score': args.min_score,
        'papers': [{'arxiv_id': paper.arxiv_id, 'title': paper.title, 'score': paper.score,
                    'interest_scores': paper.interest_scores, 'tldr': paper.tldr,
                    'pdf_url': paper.pdf_url} for paper in papers],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding='utf-8')
    output.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    logger.info('RADAR_SELECTION=' + json.dumps(report, ensure_ascii=False))
    if args.dry_run:
        logger.info(f'Preview saved to {output}; no email sent')
    elif papers or args.send_empty:
        send_email(args.sender, args.receiver, args.sender_password, args.smtp_server, args.smtp_port, html)
        logger.success('Email sent successfully')
    else:
        logger.info('No papers met the topic and score requirements; no email sent')
    return report


parser = argparse.ArgumentParser(description='Recommender system for academic papers')

def add_argument(*args, **kwargs):
    def get_env(key:str, default=None):
        # handle environment variables generated at Workflow runtime
        # Unset environment variables are passed as '', we should treat them as None
        v = os.environ.get(key)
        if v == '' or v is None:
            return default
        return v
    parser.add_argument(*args, **kwargs)
    arg_full_name = kwargs.get('dest', args[-1][2:])
    env_name = arg_full_name.upper()
    env_value = get_env(env_name)
    if env_value is not None:
        #convert env_value to the specified type
        if kwargs.get('type') == bool:
            env_value = env_value.lower() in ['true','1']
        else:
            env_value = kwargs.get('type')(env_value)
        parser.set_defaults(**{arg_full_name:env_value})

if __name__ == '__main__':
    add_argument('--send_empty', type=bool, help='If get no arxiv paper, send empty email',default=False)
    add_argument('--max_paper_num', type=int, help='Maximum number of papers to recommend',default=100)
    add_argument('--arxiv_query', type=str, help='Arxiv search query')
    add_argument('--topic_query', type=str, default=DEFAULT_TOPIC_QUERY, help='Communication topic search expression')
    add_argument('--min_score', type=float, default=70, help='Minimum relevance score for recommendations')
    add_argument('--smtp_server', type=str, help='SMTP server')
    add_argument('--smtp_port', type=int, help='SMTP port')
    add_argument('--sender', type=str, help='Sender email address')
    add_argument('--receiver', type=str, help='Receiver email address')
    add_argument('--sender_password', type=str, help='Sender email password')
    add_argument(
        "--retriever_target",
        type=str,
        help="Retriever target domain, such as 'agent' or 'software test'"
    )
    add_argument(
        "--use_llm_api",
        type=bool,
        help="Use OpenAI API to generate TLDR",
        default=False,
    )
    add_argument(
        "--openai_api_key",
        type=str,
        help="OpenAI API key",
        default=None,
    )
    add_argument(
        "--openai_api_base",
        type=str,
        help="OpenAI API base URL",
        default="https://api.openai.com/v1",
    )
    add_argument(
        "--model_name",
        type=str,
        help="LLM Model Name",
        default="gpt-4o",
    )
    add_argument(
        "--language",
        type=str,
        help="Language of TLDR",
        default="English",
    )
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    parser.add_argument('--dry_run', action='store_true', help='Save a preview without sending email')
    parser.add_argument('--output', default='output/latest.html', help='HTML preview path; JSON report is saved alongside')
    args = parser.parse_args()

    assert (
        not args.use_llm_api or args.openai_api_key is not None
    )  # If use_llm_api is True, openai_api_key must be provided
    if args.debug:
        logger.remove()
        logger.add(sys.stdout, level="DEBUG")
        logger.debug("Debug mode is on.")
    else:
        logger.remove()
        logger.add(sys.stdout, level="INFO")

    run_radar(args)
