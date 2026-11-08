"""Scope this radar to information and communication engineering."""
import re


DEFAULT_TOPIC_QUERY = ' OR '.join(f'"{phrase}"' for phrase in (
    'semantic communication', 'semantic communications', 'DeepJSCC',
    'joint source-channel coding', 'joint source channel coding',
    'underwater acoustic communication', 'underwater acoustic communications',
    'underwater optical communication', 'underwater wireless optical communication',
    'optical wireless communication', 'visible light communication',
    'free-space optical communication', 'optical fiber communication',
    'fiber-optic communication', 'acoustic-optical communication',
    'hybrid acoustic optical',
))


def is_target_communication(paper):
    text = f'{paper.title}\n{paper.summary}'.casefold()
    text = re.sub(r'[-\u2010-\u2015_/]+', ' ', text)
    if re.search(r'\bsemantic\s+communications?\b|\bdeep\s*jscc\b|\bjoint\s+source\s+channel\b', text):
        return True
    communication_context = re.search(
        r'\bcommunications?\b|\btransceivers?\b|\bmodulation\b|\bdemodulation\b|'
        r'\bequali[sz]ation\b|\bbit\s+error\b|\bspectral\s+efficiency\b|'
        r'\bchannel\s+(?:estimation|model(?:ing|ling)?|impulse\s+response|capacity)\b|'
        r'\bdata\s+(?:rate|transmission)\b|\breceivers?\b|\btransmitters?\b|'
        r'\bofdm\b|\bber\b|\bmimo\b|\bqam\b', text,
    )
    if not communication_context:
        return False
    underwater_acoustic = 'underwater' in text and 'acoustic' in text
    optical_link = re.search(r'\boptical\b|\boptic\b|\bfib(?:er|re)\b|\bvisible\s+light\b', text)
    return bool(underwater_acoustic or optical_link)
