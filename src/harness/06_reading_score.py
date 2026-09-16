"""Harness step 6: Urdu + English reading scores from STT alone (the "cheap stack").
For each child and each reading subtask (orf_urd, idwrd_urd, orf_eng, idwrd_eng, pw_eng), take the child's words
inside the LLM-labelled window (Soniox timestamps), align them to the reconstructed reference with the same
Levenshtein alignment FluencyService uses, and count correct / attempted. Compare to the enumerator's counts
(`*_60s_correct`, `*_reading_correct`, `*_attempted`) and, per word, to the enumerator's item flags.
Run: uv run --with pandas python harness/06_reading_score.py
"""
import os, json, glob, re, collections
import pandas as pd

SEG_MODEL = 'google_gemini-2.5-pro'
SUBS = {'orf_urd': 'orf', 'idwrd_urd': 'idwrd', 'orf_eng': 'orf', 'idwrd_eng': 'idwrd', 'pw_eng': 'pw', 'letterid_urd': 'lid', 'letterid_eng': 'lid'}

UR_MAP = str.maketrans({'ي': 'ی', 'ك': 'ک', 'ه': 'ہ', 'ۂ': 'ہ', 'ۀ': 'ہ', 'ے': 'ی', 'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ؤ': 'و', 'ئ': 'ی', 'ة': 'ہ'})
DIAC = re.compile('[ً-ٰٟۖ-ۭ​-‏]')
PUNC = re.compile('[؀-؅،؛؟٪-٭۔.,!?;:"\'()\-–—]')
def clean(w):
    w = DIAC.sub('', w)
    w = PUNC.sub('', w)
    w = w.translate(UR_MAP).replace('ھ', 'ہ')
    return w.strip().lower()

def same(a, b):
    if a == b:
        return True
    if min(len(a), len(b)) < 4 or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(1 for x, y in zip(a, b) if x != y) == 1
    if len(a) > len(b):
        a, b = b, a
    return any(b[:i] + b[i + 1:] == a for i in range(len(b)))

def enumerator_speaker(tr):
    tot = collections.Counter()
    for t in tr.get('tokens', []):
        tot[t.get('speaker')] += t.get('end_ms', 0) - t.get('start_ms', 0)
    return tot.most_common(1)[0][0] if tot else None

def child_tokens(tr, s, e, all_speakers=True):
    esp = None if all_speakers else enumerator_speaker(tr)
    out = []
    for t in tr.get('tokens', []):
        ts, te = t.get('start_ms', 0) / 1000, t.get('end_ms', 0) / 1000
        if ts >= s - 0.2 and te <= e + 0.2 and (esp is None or t.get('speaker') != esp):
            out.append(t)
    return out

def words_with_time(toks):
    """Soniox tokens are sub-word; rebuild words and keep first-token start time."""
    words = []; cur = ''; st = None
    for t in toks:
        tx = t.get('text', '')
        if tx.startswith(' ') or not cur:
            if cur.strip():
                words.append((clean(cur), st))
            cur = tx; st = t.get('start_ms', 0) / 1000
        else:
            cur += tx
    if cur.strip():
        words.append((clean(cur), st))
    return [(w, s) for w, s in words if w]

def align(ref, hyp):
    """Levenshtein alignment; returns per-ref-word status (correct/sub/omit) and insertion count."""
    n, m = len(ref), len(hyp)
    D = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1): D[i][0] = i
    for j in range(m + 1): D[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            c = 0 if same(ref[i - 1], hyp[j - 1]) else 1
            D[i][j] = min(D[i - 1][j] + 1, D[i][j - 1] + 1, D[i - 1][j - 1] + c)
    i, j = n, m; status = ['omit'] * n; ins = 0
    while i > 0 or j > 0:
        if i > 0 and j > 0 and D[i][j] == D[i - 1][j - 1] + (0 if same(ref[i - 1], hyp[j - 1]) else 1):
            status[i - 1] = 'correct' if same(ref[i - 1], hyp[j - 1]) else 'sub'; i -= 1; j -= 1
        elif i > 0 and D[i][j] == D[i - 1][j] + 1:
            status[i - 1] = 'omit'; i -= 1
        else:
            ins += 1; j -= 1
    return status, ins

def last_attempted(status):
    idx = [i for i, s in enumerate(status) if s != 'omit']
    return (idx[-1] + 1) if idx else 0

if __name__ == '__main__':
    refs = {}
    for sub in SUBS:
        p = f'harness/reference/{sub}.json'
        if os.path.exists(p):
            refs[sub] = json.load(open(p))['ref']
    print('references:', {k: len(v) for k, v in refs.items()})
    rows = []; item_rows = []
    for p in glob.glob(f'harness/segments_llm/{SEG_MODEL}__*.json'):
        r = json.load(open(p)); f = r['file']
        trp, gtp = 'harness/soniox/' + f, 'harness/gt/' + f
        if not (os.path.exists(trp) and os.path.exists(gtp)):
            continue
        tr_ur = json.load(open(trp)); gt = json.load(open(gtp)); sc = gt['scores']
        tr_en = json.load(open('harness/whisper_en/' + f)) if os.path.exists('harness/whisper_en/' + f) else None
        for s in r['segments']:
            sub = s['sub']
            if sub not in refs:
                continue
            tr = tr_en if (sub.endswith('_eng') and tr_en) else tr_ur
            if sub.endswith('_eng') and not tr_en:
                continue
            toks = child_tokens(tr, s['start_s'], s['end_s'])
            wt = words_with_time(toks)
            if not wt:
                continue
            # 60-second window from the child's first word (the toolkit's timer starts at "start")
            t0 = wt[0][1]
            hyp60 = [w for w, t in wt if t - t0 <= 60.5]
            status, ins = align(refs[sub], hyp60)
            att = last_attempted(status); corr = sum(1 for x in status[:att] if x == 'correct')
            lang = 'urd' if sub.endswith('urd') else 'eng'; pre = SUBS[sub]
            # enumerator counts: prefer the 60 s milestone fields, else the full-task fields
            e_corr = sc.get(f'{pre}_60s_correct_{lang}') or sc.get(f'{pre}_reading_correct_{lang}')
            e_att = sc.get(f'{pre}_60s_attempted_{lang}') or sc.get(f'{pre}_reading_attempted_{lang}')
            rows.append(dict(file=f[:20], sub=sub, machine_correct=corr, machine_attempted=att, machine_ins=ins, enum_correct=e_corr, enum_attempted=e_att,
                             child_words=len(hyp60), grade=gt.get('grade'), conf=s.get('confidence')))
            # per-item comparison with the enumerator's flags (1 = incorrect)
            flags = gt['items'].get(sub)
            if flags and e_att not in (None, ''):
                # the export writes 0 for BOTH 'read correctly' and 'never reached': compare only words both sides reached
                reach = min(att, int(float(e_att)), len(flags))
                for i in range(reach):
                    if flags[i] is not None:
                        item_rows.append(dict(sub=sub, machine_wrong=int(status[i] != 'correct'), enum_wrong=int(flags[i])))
    df = pd.DataFrame(rows)
    df.to_csv('harness/reading_scores.csv', index=False)
    for sub, d in df.groupby('sub'):
        d = d.dropna(subset=['enum_correct'])
        d = d.assign(enum_correct=pd.to_numeric(d.enum_correct), enum_attempted=pd.to_numeric(d.enum_attempted))
        if len(d) < 3:
            print(sub, 'n', len(d)); continue
        r_c = d.machine_correct.corr(d.enum_correct); mae = (d.machine_correct - d.enum_correct).abs().mean(); bias = (d.machine_correct - d.enum_correct).mean()
        w3 = ((d.machine_correct - d.enum_correct).abs() <= 3).mean()
        print(f"{sub:10s} n={len(d):3d} correct: r={r_c:.2f} MAE={mae:.1f} bias={bias:+.1f} within±3={100 * w3:.0f}% | attempted: r={d.machine_attempted.corr(d.enum_attempted):.2f} MAE={(d.machine_attempted - d.enum_attempted).abs().mean():.1f}")
    it = pd.DataFrame(item_rows)
    if len(it):
        for sub, d in it.groupby('sub'):
            tp = ((d.machine_wrong == 1) & (d.enum_wrong == 1)).sum(); fp = ((d.machine_wrong == 1) & (d.enum_wrong == 0)).sum(); fn = ((d.machine_wrong == 0) & (d.enum_wrong == 1)).sum()
            prec = tp / max(1, tp + fp); rec = tp / max(1, tp + fn)
            print(f"  per-word {sub:10s} items={len(d):5d} enum_error_rate={d.enum_wrong.mean():.2f} machine_error_rate={d.machine_wrong.mean():.2f} miscue precision={prec:.2f} recall={rec:.2f} agreement={(d.machine_wrong == d.enum_wrong).mean():.2f}")
        it.to_csv('harness/reading_items.csv', index=False)
