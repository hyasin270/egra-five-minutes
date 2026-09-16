"""Harness step 3: rule-based segmenter over Soniox diarised tokens.
For every transcribed recording, find subtask windows from the enumerator's cue phrases and the child's
speech, then compare the recovered timed-window starts/lengths with the tablet's own timestamps.
Writes harness/segments/<file>.json and prints agreement stats.
Run: uv run --with pandas python harness/03_segmenter.py
"""
import os, json, re, glob, datetime as dt
import pandas as pd

os.makedirs('harness/segments', exist_ok=True)

# Cue phrases per subtask (Urdu script + romanised + English), matched on the enumerator's turns.
CUES = {
    'listcomp_urd': [r'سٹوری سنا', r'اسٹوری سنا', r'کہانی سنا', r'story suna'],
    'letterid_urd': [r'حروف', r'یہ پڑھو', r'اونچی آواز', r'سٹارٹ کرو', r'اسٹارٹ'],
    'idwrd_urd': [r'الفاظ', r'یہ پڑھنا آتا', r'لفظ'],
    'orf_urd': [r'سٹوری پڑھو', r'اسٹوری پڑھو', r'کہانی پڑھو', r'پیراگراف'],
    'listcomp_eng': [r'انگلش میں.*سٹوری', r'انگریزی.*کہانی', r'english story', r'story in english'],
    'letterid_eng': [r'letters?', r'انگلش.*حروف', r'alphabet'],
    'pw_eng': [r'made.?up words', r'nonsense', r'not real words', r'فرضی', r'بناوٹی', r'پورا.*ورڈ'],
    'idwrd_eng': [r'\bwords?\b', r'ورڈز', r'انگلش.*الفاظ'],
    'orf_eng': [r'read (this|the) story', r'read.*passage', r'انگلش.*سٹوری پڑھ'],
    'math': [r'بڑا نمبر', r'کون ?سا نمبر', r'نمبر', r'number', r'گنتی', r'جمع', r'تفریق', r'plus', r'minus'],
}

def load_tokens(path):
    tr = json.load(open(path))
    toks = tr.get('tokens', [])
    out = []
    for t in toks:
        out.append({'t': t.get('text', ''), 's': t.get('start_ms', 0) / 1000.0, 'e': t.get('end_ms', 0) / 1000.0,
                    'spk': t.get('speaker'), 'lang': t.get('language')})
    return out

def turns(tokens):
    """Group consecutive same-speaker tokens into turns."""
    res = []
    for tk in tokens:
        if res and res[-1]['spk'] == tk['spk'] and tk['s'] - res[-1]['e'] < 2.0:
            res[-1]['text'] += tk['t']; res[-1]['e'] = tk['e']; res[-1]['n'] += 1
        else:
            res.append({'spk': tk['spk'], 's': tk['s'], 'e': tk['e'], 'text': tk['t'], 'n': 1})
    return res

def enumerator_speaker(tks):
    """The enumerator is the speaker with the most total speech."""
    tot = {}
    for tk in tks:
        tot[tk['spk']] = tot.get(tk['spk'], 0) + (tk['e'] - tk['s'])
    return max(tot, key=tot.get) if tot else None

def child_runs(tks, enum_spk, min_len=25.0):
    """Long continuous non-enumerator speech = a timed read (letters, words, passage)."""
    runs = []
    cur = None
    for tk in tks:
        if tk['spk'] == enum_spk:
            continue
        if cur and tk['s'] - cur['e'] < 4.0:
            cur['e'] = tk['e']; cur['n'] += 1; cur['text'] += tk['t']
        else:
            if cur: runs.append(cur)
            cur = {'s': tk['s'], 'e': tk['e'], 'n': 1, 'text': tk['t']}
    if cur: runs.append(cur)
    return [r for r in runs if r['e'] - r['s'] >= min_len]

def segment(path):
    tks = load_tokens(path)
    if not tks:
        return None
    esp = enumerator_speaker(tks)
    tr = turns(tks)
    cues = []
    for tu in tr:
        if tu['spk'] != esp:
            continue
        for k, pats in CUES.items():
            for p in pats:
                if re.search(p, tu['text'], re.I):
                    cues.append({'sub': k, 's': tu['s'], 'text': tu['text'][:80]}); break
    runs = child_runs(tks, esp)
    return {'file': os.path.basename(path), 'enum_spk': esp, 'n_tokens': len(tks), 'duration': tks[-1]['e'],
            'cues': cues, 'child_runs': [{'s': round(r['s'], 1), 'e': round(r['e'], 1), 'len': round(r['e'] - r['s'], 1), 'n': r['n'], 'head': r['text'][:60]} for r in runs]}

def compare(seg, gt):
    """Tablet timed subtasks (letterid/idwrd/orf ×2, blfluency) vs recovered child runs.
    Fit one offset (recording start) by matching the tablet's letterid_urd start to the first long child run."""
    st = gt['subtask_times']
    def T(k, w):
        v = st.get(k, {}).get(w)
        return pd.to_datetime(v) if v else None
    tablet = []
    for k in ['letterid_urd', 'idwrd_urd', 'orf_urd', 'letterid_eng', 'pw_eng', 'idwrd_eng', 'orf_eng']:
        a, b = T(k, 'start'), T(k, 'end')
        if a is not None and b is not None and 0 < (b - a).total_seconds() < 600:
            tablet.append({'sub': k, 'start': a, 'len': (b - a).total_seconds()})
    if not tablet or not seg['child_runs']:
        return None
    # candidate offsets: align each child run start to the tablet letterid_urd start (+~8 s instruction lag)
    ref = next((t for t in tablet if t['sub'] == 'letterid_urd'), tablet[0])
    best = None
    for r in seg['child_runs']:
        off = (ref['start'] - pd.Timestamp(gt['form_start'])).total_seconds() if gt.get('form_start') else 0
        # offset = seconds into the recording where the tablet's ref subtask started
        cand_off = r['s'] - 8.0  # recording second at which tablet 'start' would sit
        # score: how many tablet subtasks have a child run starting within 20 s of (tablet_start - ref_start + cand_off)
        hits = 0; errs = []
        for t in tablet:
            exp = cand_off + (t['start'] - ref['start']).total_seconds()
            near = [x for x in seg['child_runs'] if abs(x['s'] - exp) < 25]
            if near:
                hits += 1; errs.append(min(abs(x['s'] - exp) for x in near))
        if best is None or hits > best['hits'] or (hits == best['hits'] and sum(errs) < sum(best['errs'])):
            best = {'hits': hits, 'errs': errs, 'cand_off': cand_off}
    return {'tablet_timed': len(tablet), 'matched': best['hits'], 'mean_abs_err_s': round(sum(best['errs']) / len(best['errs']), 1) if best['errs'] else None,
            'run_lengths': [r['len'] for r in seg['child_runs']]}

if __name__ == '__main__':
    rows = []
    for p in sorted(glob.glob('harness/soniox/*.json')):
        seg = segment(p)
        if not seg:
            continue
        json.dump(seg, open('harness/segments/' + os.path.basename(p), 'w'), ensure_ascii=False)
        gtp = 'harness/gt/' + os.path.basename(p)
        cmp_ = compare(seg, json.load(open(gtp))) if os.path.exists(gtp) else None
        rows.append({'file': seg['file'][:24], 'dur_min': round(seg['duration'] / 60, 1), 'cues': len(seg['cues']), 'child_runs': len(seg['child_runs']),
                     'runs_55_70s': sum(1 for r in seg['child_runs'] if 55 <= r['len'] <= 70),
                     'tablet_timed': cmp_['tablet_timed'] if cmp_ else None, 'matched': cmp_['matched'] if cmp_ else None, 'err_s': cmp_['mean_abs_err_s'] if cmp_ else None})
    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    if len(df):
        print('\nfiles', len(df), '| mean child runs', df.child_runs.mean().round(1), '| mean 55-70s runs', df.runs_55_70s.mean().round(1),
              '| matched/tablet', df.matched.sum(), '/', df.tablet_timed.sum(), '| mean |err| s', df.err_s.mean().round(1) if df.err_s.notna().any() else None)
    df.to_csv('harness/segmenter_results.csv', index=False)
