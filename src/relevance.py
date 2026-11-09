"""Select semantic communication methods independently of application scenario."""
import re


DEFAULT_ARXIV_QUERY = 'cs.IT+eess.SP+eess.IV+cs.CV+cs.MM+cs.LG+cs.CL+eess.AS+cs.NI'

DEFAULT_INTERESTS = '\n'.join((
    'Semantic communication and deep joint source-channel coding methods in any modality and application; FAJSCC and MambaJSCC as references',
    'Task-oriented semantic coding, feature selection, generative and multimodal semantic transmission for reconstruction or receiver inference',
    'ResiComp-style loss-resilient learned source/latent coding, masked tokens and packet-loss concealment for communication',
    'Low-complexity, compute-adaptive, variable-rate and SNR/CSI-adaptive semantic communication and DeepJSCC',
    'Applications of semantic communication and DeepJSCC to underwater acoustic, optical, hybrid acoustic-optical and other communication channels',
))

DEFAULT_TOPIC_QUERY = ' OR '.join(f'"{phrase}"' for phrase in (
    'ResiComp', 'FAJSCC', 'MambaJSCC', 'DeepJSCC', 'SwinJSCC', 'NTSCC',
    'joint source-channel coding', 'joint source channel coding',
    'deep source channel coding', 'semantic communication', 'semantic communications',
    'semantic transmission', 'semantic coding', 'semantic autoencoder', 'SemCom',
    'token communication',
)) + ' OR ((neural OR learned OR learning) AND (compression OR codec) AND (' + ' OR '.join(
    f'"{phrase}"' for phrase in ('packet loss', 'loss-resilient', 'erasure-resilient', 'loss concealment')
) + '))'


def is_target_communication(paper):
    text = f'{paper.title}\n{paper.summary}'.casefold()
    text = re.sub(r'[-\u2010-\u2015_/]+', ' ', text)
    title = text.split('\n', 1)[0]
    if re.search(r'\b(?:resicomp|fajscc|mambajscc|swinjscc|ntscc)\b|'
                 r'\bnonlinear\s+transform\s+source\s+channel\s+coding\b', title):
        return True
    learned = re.search(r'\b(?:learned|learning|neural|deep|transformer|mamba|generative|autoencoder)\b', text)
    semantic_coding = re.search(
        r'\bsemcom\b|\b(?:semantic|token)\s+(?:(?:\w+)\s+){0,3}(?:communications?|transmission)\b', text,
    )
    if semantic_coding:
        return True
    communication_context = re.search(r'\b(?:communications?|transmission|channels?|wireless|links?)\b', text)
    semantic_codec = re.search(r'\bsemantic\s+(?:coding|codecs?|encoders?|decoders?|autoencoders?)\b', text)
    if semantic_codec and communication_context:
        return True
    jscc = re.search(r'\b[a-z0-9]*jscc\b|\bntscc\b|\bsource\s+channel\s+coding\b', text)
    if jscc and learned:
        return True
    # ResiComp-style codecs can be highly relevant without calling themselves JSCC.
    codec = re.search(r'\b(?:compression|codecs?|coding)\b', text)
    resilient = re.search(
        r'\bpacket\s+(?:loss(?:es)?|erasures?)\b|\b(?:loss|erasure|error)\s+resilien\w*\b|'
        r'\b(?:loss|error)\s+concealment\b', text,
    )
    return bool(learned and codec and resilient)
