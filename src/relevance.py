"""Scope the radar to learned visual coding and robust semantic transmission."""
import re


DEFAULT_ARXIV_QUERY = 'cs.IT+eess.SP+eess.IV+cs.CV+cs.MM+cs.LG'

DEFAULT_INTERESTS = '\n'.join((
    'DeepJSCC image/video encoder and decoder architectures, especially FAJSCC and MambaJSCC',
    'Loss-resilient learned image/video compression, masked visual tokens and packet-loss concealment, as in ResiComp',
    'Low-complexity, compute-adaptive, SNR/CSI-adaptive and variable-rate visual JSCC',
    'Generative image/video transmission using diffusion, discrete tokens and semantic refinement',
    'Semantic or learned robust image/video transmission over underwater acoustic, optical or hybrid acoustic-optical links',
))

DEFAULT_TOPIC_QUERY = ' OR '.join(f'"{phrase}"' for phrase in (
    'ResiComp', 'FAJSCC', 'MambaJSCC', 'DeepJSCC', 'SwinJSCC', 'NTSCC',
    'joint source-channel coding', 'joint source channel coding',
    'deep source channel coding',
)) + ' OR ((image OR video OR visual) AND (' + ' OR '.join(
    f'"{phrase}"' for phrase in (
        'semantic communication', 'semantic communications', 'token communication',
        'loss-resilient image', 'loss-resilient video', 'packet loss concealment',
        'erasure-resilient codec',
    )
) + '))'


def is_target_communication(paper):
    text = f'{paper.title}\n{paper.summary}'.casefold()
    text = re.sub(r'[-\u2010-\u2015_/]+', ' ', text)
    title = text.split('\n', 1)[0]
    if re.search(r'\b(?:resicomp|fajscc|mambajscc|swinjscc|ntscc)\b|'
                 r'\bnonlinear\s+transform\s+source\s+channel\s+coding\b', title):
        return True
    if not re.search(r'\b(?:images?|videos?|visual|multimedia|pictures?)\b', text):
        return False
    semantic_coding = re.search(
        r'\b[a-z0-9]*jscc\b|\bntscc\b|\bsource\s+channel\s+coding\b|'
        r'\b(?:semantic|token)\s+(?:communications?|transmission|codecs?)\b|'
        r'\bsemantic\s+(?:image|video|visual|multimedia)\s+(?:communications?|transmission|coding)\b', text,
    )
    if semantic_coding:
        return True
    # ResiComp-style codecs can be highly relevant without calling themselves JSCC.
    learned = re.search(r'\b(?:learned|learning|neural|transformer|generative)\b', text)
    codec = re.search(r'\b(?:compression|codecs?|coding)\b', text)
    resilient = re.search(
        r'\bpacket\s+(?:loss(?:es)?|erasures?)\b|\b(?:loss|erasure|error)\s+resilien\w*\b|'
        r'\b(?:loss|error)\s+concealment\b', text,
    )
    return bool(learned and codec and resilient)
