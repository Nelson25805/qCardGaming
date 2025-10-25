"""
quiz_loader.py
Functions to load question CSVs and generate distractors.
"""

import csv
import random

def load_questions(csv_path):
    rows = []
    with open(csv_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r.get('question') and r.get('answer'):
                rows.append({'id': r.get('id'), 'q': r['question'], 'a': r['answer'], 'subject': r.get('subject',''), 'difficulty': r.get('difficulty','')})
    return rows

def is_number(s):
    try:
        float(s)
        return True
    except:
        return False

def make_distractors(correct, pool):
    candidates = set()
    if is_number(correct):
        try:
            val = float(correct)
            nums = [val-1, val+1, val+2, val-2, val*10]
            for n in nums:
                if len(candidates) >= 3:
                    break
                if n != val:
                    s = str(int(n)) if abs(n - int(n)) < 1e-9 else str(n)
                    if s != correct:
                        candidates.add(s)
        except:
            pass
    for p in pool:
        if len(candidates) >= 3:
            break
        if p != correct:
            candidates.add(p)
    i = 0
    while len(candidates) < 3:
        candidates.add(f"{correct}_alt{i}")
        i += 1
    res = list(candidates)[:3]
    random.shuffle(res)
    return res
