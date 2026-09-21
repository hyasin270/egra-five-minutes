"""Harness step 4: reconstruct the instrument's reference texts by consensus across children.
The SurveyCTO export carries only per-item correct/incorrect flags, not the stimulus text. But 100+ children read
the same Urdu passage, the same word list, the same English passage. Take each child's transcript inside the
LLM-labelled window, align all of them with a positional majority vote, and recover the reference.
Output: harness/reference/<subtask>.txt + a confidence report.
Run: uv run --with pandas python harness/04_reference_reconstruct.py
"""
import os, json, glob, re, collections
import pandas as pd

os.makedirs('harness/reference', exist_ok=True)
SEG_MODEL = 'google_gemini-2.5-pro'
URDU_RE = re.compile(r'[؀-ۿ]')

def tokens_in(tr, s, e, enum_spk=None):
    out = []
    for t in tr.get('tokens', []):
        ts, te = t.get('start_ms', 0) / 1000, t.get('end_ms', 0) / 1000
        if ts >= s - 0.2 and te <= e + 0.2:
            out.append(t)
    return out

def clean(w):
    w = re.sub(r'[؀-؅،؛؟٪-٭۔.,!?;:"\'()\-–—]', '', w)
    return w.strip().lower()

def words(toks):
    txt = ''.join(t.get('text', '') for t in toks)
    return [clean(w) for w in txt.split() if clean(w)]

def enumerator_speaker(tr):
    tot = collections.Counter()
    for t in tr.get('tokens', []):
        tot[t.get('speaker')] += t.get('end_ms', 0) - t.get('start_ms', 0)
    return tot.most_common(1)[0][0] if tot else None

def child_words(tr, s, e):
    esp = enumerator_speaker(tr)
    toks = [t for t in tokens_in(tr, s, e) if t.get('speaker') != esp]
    return words(toks)

def consensus(seqs, min_support=0.25):
    """Progressive alignment: seed with the longest sequence, align others by LCS-ish DP, vote per column."""
    if not seqs:
        return [], []
    seqs = sorted(seqs, key=len, reverse=True)
    ref = list(seqs[0]); votes = [collections.Counter([w]) for w in ref]
    for sq in seqs[1:]:
        # DP alignment (edit distance with backtrace), match = same string
        n, m = len(ref), len(sq)
        D = [[0] * (m + 1) for _ in range(n + 1)]
        for i in range(n + 1): D[i][0] = i
        for j in range(m + 1): D[0][j] = j
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                c = 0 if ref[i - 1] == sq[j - 1] else 1
                D[i][j] = min(D[i - 1][j] + 1, D[i][j - 1] + 1, D[i - 1][j - 1] + c)
        i, j = n, m
        while i > 0 and j > 0:
            c = 0 if ref[i - 1] == sq[j - 1] else 1
            if D[i][j] == D[i - 1][j - 1] + c:
                votes[i - 1][sq[j - 1]] += 1; i -= 1; j -= 1
            elif D[i][j] == D[i - 1][j] + 1:
                i -= 1
            else:
                j -= 1
    out, conf = [], []
    for v in votes:
        w, c = v.most_common(1)[0]
        tot = sum(v.values())
        if tot >= max(3, min_support * len(seqs)):
            out.append(w); conf.append(round(c / tot, 2))
    return out, conf

if __name__ == '__main__':
    per_sub = collections.defaultdict(list)
    n_files = 0
    for p in glob.glob(f'harness/segments_llm/{SEG_MODEL}__*.json'):
        r = json.load(open(p)); f = r['file']
        trp = 'harness/soniox/' + f
        if not os.path.exists(trp):
            continue
        tr_ur = json.load(open(trp)); n_files += 1
        tr_en = json.load(open('harness/soniox_en/' + f)) if os.path.exists('harness/soniox_en/' + f) else None
        for s in r['segments']:
            tr = tr_en if (s['sub'].endswith('_eng') and tr_en) else tr_ur
            if s['sub'].endswith('_eng') and not tr_en:
                continue
            if s['sub'] in ('orf_urd', 'idwrd_urd', 'orf_eng', 'idwrd_eng', 'pw_eng', 'letterid_urd', 'letterid_eng') and (s.get('confidence') or 0) >= 0.7:
                cw = child_words(tr, s['start_s'], s['end_s'])
                if len(cw) >= 8:
                    per_sub[s['sub']].append(cw)
    print('files', n_files)
    for sub, seqs in per_sub.items():
        ref, conf = consensus(seqs)
        open(f'harness/reference/{sub}.txt', 'w').write(' '.join(ref))
        json.dump({'sub': sub, 'n_children': len(seqs), 'ref': ref, 'conf': conf}, open(f'harness/reference/{sub}.json', 'w'), ensure_ascii=False)
        lowc = sum(1 for c in conf if c < 0.6)
        print(f"{sub:12s} children={len(seqs):3d} ref_len={len(ref):3d} mean_conf={sum(conf) / max(1, len(conf)):.2f} low_conf_positions={lowc}")
        print('   ', ' '.join(ref[:40]))
