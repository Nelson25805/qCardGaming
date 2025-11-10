"""
quiz_loader.py
Functions to load question CSVs and generate distractors.
"""

import random
import difflib
import re
import csv
from typing import List, Dict


def load_questions(csv_path: str) -> List[Dict]:
    """
    Read a CSV of questions and return a list of dicts with keys:
    'id', 'q' (question), 'a' (answer), 'subject', 'difficulty'.
    Ignores rows missing question or answer.
    """
    rows = []
    try:
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                # require both question and answer
                if r.get("question") and r.get("answer"):
                    rows.append(
                        {
                            "id": r.get("id", ""),
                            "q": r.get("question", "").strip(),
                            "a": r.get("answer", "").strip(),
                            "subject": r.get("subject", "").strip(),
                            "difficulty": r.get("difficulty", "").strip(),
                        }
                    )
    except FileNotFoundError:
        # return empty list if file missing (SpaceGame already handles empty)
        return []
    except Exception:
        # defensive: don't raise at import time — return whatever we've read so far
        return rows
    return rows


def is_number(s):
    """Return True if s looks like a number (int or float)."""
    if s is None:
        return False
    s = str(s).strip()
    # allow things like "-3", "2.5", "3e2"
    try:
        float(s)
        return True
    except Exception:
        return False


def _fmt_number(n):
    # show as int if exact integer, otherwise strip trailing zeros
    if abs(n - int(n)) < 1e-9:
        return str(int(n))
    # avoid too many decimals
    s = f"{n:.6f}".rstrip("0").rstrip(".")
    return s


def _simple_typo(word):
    # produce a mild typo variant: swap two internal chars, or replace a vowel
    if len(word) <= 2:
        return word + "x"
    w = list(word)
    # try swap
    i = random.randint(1, max(1, len(w) - 2))
    w[i], w[i + 1 if i + 1 < len(w) else i - 1] = (
        w[i + 1 if i + 1 < len(w) else i - 1],
        w[i],
    )
    swapped = "".join(w)
    if swapped.lower() != word.lower():
        return swapped
    # fallback vowel change
    vowels = "aeiou"
    for i, ch in enumerate(word):
        if ch.lower() in vowels:
            repl = random.choice(vowels.replace(ch.lower(), "") or vowels)
            new = word[:i] + (repl.upper() if ch.isupper() else repl) + word[i + 1 :]
            if new.lower() != word.lower():
                return new
    return word + "1"


def _swap_words_phrase(phrase):
    parts = phrase.split()
    if len(parts) <= 1:
        return phrase
    random.shuffle(parts)
    return " ".join(parts)


def _wordnet_synonyms(term):
    # optional: returns a small list of synonyms if nltk.wordnet is available
    try:
        from nltk.corpus import wordnet as wn
    except Exception:
        return []
    res = set()
    for syn in wn.synsets(term):
        for lemma in syn.lemmas():
            name = lemma.name().replace("_", " ")
            if name.lower() != term.lower():
                res.add(name)
            if len(res) >= 8:
                break
        if len(res) >= 8:
            break
    return list(res)


def make_distractors(correct, pool, n=3):
    """
    Return a list of n distractor strings for the given correct answer.
    Pool should be an iterable of other answer strings (e.g. from the CSV).
    """
    if correct is None:
        correct = ""
    correct = str(correct).strip()
    pool = [str(p).strip() for p in pool if p is not None and str(p).strip() != ""]
    # remove exact matches in pool (we'll still allow some pool items if different)
    pool = [p for p in pool if p.lower() != correct.lower()]

    candidates = []
    seen = set()

    def add_candidate(x):
        if not x:
            return
        s = str(x).strip()
        key = s.lower()
        if key == correct.lower():
            return
        if key in seen:
            return
        seen.add(key)
        candidates.append(s)

    # 1) Numeric heuristics
    if is_number(correct):
        try:
            val = float(correct)
            # detect reasonable "year" if integer in plausible range
            if abs(val - int(val)) < 1e-9:
                ival = int(val)
            else:
                ival = None
            # year-like
            if ival is not None and 1000 <= ival <= 2100:
                for d in (1, -1, 5, -5, 10, -10):
                    add_candidate(str(ival + d))
            else:
                # general numeric candidates
                for nval in (
                    val - 1,
                    val + 1,
                    val - 2,
                    val + 2,
                    val * 10,
                    val / 10 if val != 0 else val + 3,
                ):
                    add_candidate(_fmt_number(nval))
                # small random nearby options
                for _ in range(5):
                    jitter = val + random.choice([-3, -2, -1, 1, 2, 3]) * (
                        0.5 if abs(val) < 10 else 1
                    )
                    add_candidate(_fmt_number(jitter))
        except Exception:
            pass

    # 2) Candidates from pool that are close (string similarity) - prefer human-written answers
    # use difflib to get close matches
    try:
        matches = difflib.get_close_matches(correct, pool, n=20, cutoff=0.55)
    except Exception:
        matches = []
    for m in matches:
        add_candidate(m)
        if len(candidates) >= n:
            break

    # 3) Word-level transforms (typos, swap words, pluralize)
    if len(candidates) < n:
        # short single-word: try typos/plural forms
        if " " not in correct.strip():
            add_candidate(_simple_typo(correct))
            if not correct.endswith("s"):
                add_candidate(correct + "s")
            else:
                add_candidate(correct.rstrip("s") or correct + "1")
        else:
            # phrase variants
            add_candidate(_swap_words_phrase(correct))
            parts = correct.split()
            if len(parts) > 1:
                add_candidate(" ".join(parts[:-1]))  # drop last
                add_candidate(" ".join(parts[1:]))  # drop first
        # use some pool items of different length as more distractors
        if len(candidates) < n:
            # prefer pool answers with similar length
            pool_sorted = sorted(pool, key=lambda p: abs(len(p) - len(correct)))
            for p in pool_sorted[:12]:
                add_candidate(p)
                if len(candidates) >= n:
                    break

    # 4) try WordNet synonyms if available (helpful for single-word conceptual answers)
    if len(candidates) < n:
        for syn in _wordnet_synonyms(
            correct.split()[0] if correct.split() else correct
        ):
            add_candidate(syn)
            if len(candidates) >= n:
                break

    # 5) final fallbacks: lightweight synthetic options
    i = 0
    while len(candidates) < n and i < 30:
        cand = f"{correct}_alt{i}"
        add_candidate(cand)
        i += 1

    # shuffle the candidates so choices feel less predictable
    random.shuffle(candidates)
    return candidates[:n]
