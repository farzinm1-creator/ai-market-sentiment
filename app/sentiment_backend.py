from typing import List, Tuple
import os, yaml
from transformers import pipeline
from .sentiment_lexicon import score_texts as lexicon_scores

CFG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")
with open(CFG_PATH, "r", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

FINBERT_MODEL = CFG.get("finbert_model", "ProsusAI/finbert")
W = float(CFG.get("ensemble_weight", 0.7))
MIN_CONF = float(CFG.get("min_confidence_score", 0.55))
MIN_ABS_FOR_DAILY = float(CFG.get("min_abs_final_for_daily", 0.12))

_FINBERT_PIPE = None
def _get_finbert():
    global _FINBERT_PIPE
    if _FINBERT_PIPE is None:
        _FINBERT_PIPE = pipeline("sentiment-analysis", model=FINBERT_MODEL, tokenizer=FINBERT_MODEL)
    return _FINBERT_PIPE

def _map_label_to_signed(label: str, score: float) -> float:
    lab = (label or "").lower()
    if lab.startswith("pos"): return +score
    if lab.startswith("neg"): return -score
    return 0.0

def finbert_scores_with_conf(texts: List[str]) -> Tuple[List[float], List[float]]:
    nlp = _get_finbert()
    res = nlp(texts, truncation=True)
    scores, confs = [], []
    for r in res:
        label = r.get("label","neutral")
        sc = float(r.get("score", 0.5))
        scores.append(_map_label_to_signed(label, sc))
        confs.append(sc)
    return scores, confs

def ensemble_scores(texts: List[str]) -> Tuple[List[float], List[float], List[bool]]:
    if not texts: return [], [], []
    f_scores, f_conf = finbert_scores_with_conf(texts)
    l_scores = lexicon_scores(texts)
    final = [W*fs + (1.0 - W)*ls for fs, ls in zip(f_scores, l_scores)]
    low_flags = [(abs(fc) < MIN_CONF and abs(s) < MIN_ABS_FOR_DAILY) for fc, s in zip(f_conf, final)]
    return final, f_conf, low_flags
