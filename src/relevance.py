"""Select literature relevant to spatially assisted visual JSCC."""
import re


DEFAULT_ARXIV_QUERY = 'cs.IT+eess.SP+eess.IV+cs.CV+cs.MM+cs.LG+cs.CL+eess.AS+cs.NI'

DEFAULT_INTERESTS = '\n'.join((
    'Image and video DeepJSCC and semantic transmission for reconstruction; SwinJSCC, FAJSCC and MambaJSCC',
    'Explicit spatial or geometric priors for visual communication: 2D distances, positions, spatial relations, relative monocular depth and depth-aware attention',
    'Spatial structure, edges, topology, regions of interest and feature importance for robust image reconstruction in semantic communication',
    'SNR or CSI adaptive and bandwidth-adaptive JSCC with geometry, attention, Transformers or visual state-space models',
    'ResiComp-style loss-resilient learned image or video coding, masked tokens and packet-loss concealment for communication',
    'Spatial or geometry-aware visual representation and attention methods transferable to image communication and reconstruction',
))

DEFAULT_TOPIC_QUERY = ' OR '.join(f'"{phrase}"' for phrase in (
    'ResiComp', 'FAJSCC', 'MambaJSCC', 'DeepJSCC', 'SwinJSCC', 'NTSCC',
    'joint source-channel coding', 'joint source channel coding',
    'deep source channel coding', 'semantic communication', 'semantic communications',
    'semantic transmission', 'semantic coding', 'semantic autoencoder', 'SemCom',
    'token communication', 'spatial prior', 'geometry attention', 'depth-aware attention',
)) + ' OR ((neural OR learned OR learning) AND (compression OR codec) AND (' + ' OR '.join(
    f'"{phrase}"' for phrase in ('packet loss', 'loss-resilient', 'erasure-resilient', 'loss concealment')
) + '))'


def is_thesis_relevant(paper):
    """Keep visual communication and specific transferable geometry methods."""
    text = re.sub(r'[-\u2010-\u2015_/]+', ' ', f'{paper.title}\n{paper.summary}'.casefold())
    if re.search(r'\b(?:swinjscc|mambajscc|fajscc|resicomp)\b', text):
        return True
    visual = re.search(r'\b(?:images?|visual|vision|video|rgbd|rgb d)\b', text)
    if not visual:
        return False
    if is_target_communication(paper):
        return True
    explicit_geometry = re.search(
        r'\b(?:geometry|geometric|depth|spatial)\s+(?:aware\s+)?(?:self\s+)?attention\b|'
        r'\b(?:monocular|relative|estimated)\s+depth\b|\bdepth\s+(?:maps?|guided|aware)\b|'
        r'\b(?:rgbd|rgb d)\b|\b(?:euclidean|2d|2 d|spatial|geometric)\s+(?:distance|distances)\b|'
        r'\bgeometry\s+(?:prior|priors|guided)\b', text)
    mechanism = re.search(r'\b(?:attention|transformers?|representation|positional encoding|relative position)\b', text)
    return bool(explicit_geometry and mechanism)


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
