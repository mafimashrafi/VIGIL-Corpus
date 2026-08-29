import re

BANGLA_UNICODE_RANGE = re.compile(r"[\u0980-\u09FF]")
LATIN_ALPHA_RANGE = re.compile(r"[a-zA-Z]")
TOKEN_PATTERN = re.compile(r"[a-zA-Z]+")

BANGLISH_LEXICON = {
    "ami", "tumi", "tui", "apni", "amra", "tomra", "ora", "she", "tader",
    "amar", "tomar", "tor", "tar", "amader", "tomader",
    "ki", "keno", "kobe", "kothay", "kemon", "kivabe", "ke", "kar",
    "na", "hobe", "hoyeche", "hoise", "hoy", "hoichi", "korbo", "korchi",
    "korlam", "koris", "koren", "bolo", "bolchi", "bolche",
    "bhalo", "kharap", "sundor", "boka", "pagol", "mal", "chagol",
    "dekh", "dekhi", "dekho", "shono", "shun", "jaa", "ja", "ashi", "ashbo",
    "khai", "khabo", "khaise", "ghum", "ghumai",
    "bhai", "apu", "dada", "didi", "mama", "chacha",
    "shob", "kisu", "kichu", "onek", "ektu", "beshi", "kom",
    "ache", "nai", "nei", "chai", "lagbe", "lage",
    "bujhi", "bujhlam", "bujhte", "jani", "janina", "jantam",
    "valo", "bhalobasha", "bhalobasi", #NOTE: there could be many more
}

BANGLISH_TOKEN_RATIO_THRESHOLD = 0.25


def contains_bangla_script(text: str) -> bool:
    return bool(BANGLA_UNICODE_RANGE.search(text))


def contains_latin_script(text: str) -> bool:
    return bool(LATIN_ALPHA_RANGE.search(text))


def _banglish_token_ratio(text: str) -> float:
    tokens = [t.lower() for t in TOKEN_PATTERN.findall(text)]
    if not tokens:
        return 0.0
    matches = sum(1 for t in tokens if t in BANGLISH_LEXICON)
    return matches / len(tokens)


def detect_lang_mix(text: str) -> str:
    has_bangla = contains_bangla_script(text)
    has_latin = contains_latin_script(text)

    if has_bangla and has_latin:
        return "bn_en_mixed"
    if has_bangla and not has_latin:
        return "bn"
    if has_latin and not has_bangla:
        ratio = _banglish_token_ratio(text)
        return "banglish" if ratio >= BANGLISH_TOKEN_RATIO_THRESHOLD else "en"
    
    return "bn"