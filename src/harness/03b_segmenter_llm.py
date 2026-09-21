"""Harness step 3b: LLM-labelled segmentation on STT timestamps ("STT cuts, LLM labels").
The diarised Soniox transcript is rendered as numbered turns with start/end seconds; a TEXT LLM assigns each
subtask a first/last turn. Windows therefore inherit Soniox's timestamps. Compared against the tablet's
per-subtask start/end (relative durations + one fitted offset).
Run: uv run --with requests --with pandas python harness/03b_segmenter_llm.py [model] [max_files]
"""
import os, sys, json, glob, re, time, requests, concurrent.futures as cf
import pandas as pd

ROOT = "/Users/haroonyasin/Documents/Projects/April 2026/Rumi 10 April 2026"
KEY = [l.split('=', 1)[1].strip() for l in open(os.path.join(ROOT, '.env')) if l.startswith('NIETE_STAGING_OPENROUTER_API_KEY=')][-1]
MODEL = sys.argv[1] if len(sys.argv) > 1 else 'google/gemini-2.5-flash'
MAXF = int(sys.argv[2]) if len(sys.argv) > 2 else 10000
os.makedirs('harness/segments_llm', exist_ok=True)
SUBS = ['listcomp_urd', 'letterid_urd', 'idwrd_urd', 'orf_urd', 'rdcomp_urd', 'listcomp_eng', 'letterid_eng', 'pw_eng', 'idwrd_eng', 'orf_eng', 'rdcomp_eng',
        'idnummag', 'numrep', 'blfluency', 'bleffcomp', 'wrdpblm', 'patterns']

PROMPT = """You are segmenting a transcript of an enumerator administering an EGRA/EGMA battery to one child in a Pakistani school. The transcript is diarised and numbered; each turn has [start-end seconds] and a speaker id. The battery order is usually:
URDU: listcomp_urd (enumerator reads a story twice, asks 6 questions) → letterid_urd (child names Urdu letters for 60 s after "start") → idwrd_urd (child reads a list of Urdu words) → orf_urd (child reads an Urdu story/passage aloud) → rdcomp_urd (questions about that passage)
ENGLISH: listcomp_eng (English story + questions) → letterid_eng (English letters, 60 s) → pw_eng (made-up/nonsense words) → idwrd_eng (English word list) → orf_eng (English passage) → rdcomp_eng (questions)
MATH: idnummag (which number is bigger / identify numbers) → numrep (represent numbers, sticks/bundles, place value) → blfluency (rapid addition then subtraction, timed) → bleffcomp (computation like 25+7) → wrdpblm (word problems) → patterns (shape/number patterns)
Some subtasks may be skipped. For every subtask you can identify, output the turn number where the CHILD'S RESPONSE begins (for timed reads: the child's first letter/word after the enumerator says start; for question tasks: the first question) and the turn number where it ends. Also output the turn number of the enumerator's instruction that introduced it.
Return ONLY JSON: {"segments":[{"sub":"letterid_urd","instr_turn":12,"first_turn":13,"last_turn":14,"confidence":0.9}, ...]}"""


def render(path):
    tr = json.load(open(path))
    toks = tr.get('tokens', [])
    turns = []
    for t in toks:
        s, e, sp, tx = t.get('start_ms', 0) / 1000, t.get('end_ms', 0) / 1000, t.get('speaker'), t.get('text', '')
        if turns and turns[-1]['spk'] == sp and s - turns[-1]['e'] < 1.5:
            turns[-1]['text'] += tx; turns[-1]['e'] = e
        else:
            turns.append({'spk': sp, 's': s, 'e': e, 'text': tx})
    lines = [f"{i} [{tu['s']:.0f}-{tu['e']:.0f}] spk{tu['spk']}: {tu['text'].strip()[:400]}" for i, tu in enumerate(turns)]
    return turns, '\n'.join(lines)


def label(path):
    out = f"harness/segments_llm/{MODEL.replace('/', '_')}__{os.path.basename(path)}"
    if os.path.exists(out):
        return json.load(open(out))
    turns, text = render(path)
    for attempt in range(3):
        try:
            r = requests.post('https://openrouter.ai/api/v1/chat/completions', headers={'Authorization': f'Bearer {KEY}'},
                              json={'model': MODEL, 'messages': [{'role': 'user', 'content': PROMPT + '\n\nTRANSCRIPT:\n' + text}], 'max_tokens': 16000, 'temperature': 0}, timeout=300)
            j = r.json(); c = j['choices'][0]['message']['content']
            m = re.search(r'\{.*\}', c, re.S); segs = json.loads(m.group(0))['segments']
            res = {'file': os.path.basename(path), 'model': MODEL, 'cost': j.get('usage', {}).get('cost'), 'segments': []}
            for sg in segs:
                try:
                    ft, lt, it = int(sg['first_turn']), int(sg['last_turn']), int(sg.get('instr_turn', sg['first_turn']))
                    res['segments'].append({'sub': sg['sub'], 'instr_s': turns[it]['s'], 'start_s': turns[ft]['s'], 'end_s': turns[lt]['e'], 'confidence': sg.get('confidence')})
                except Exception:
                    pass
            json.dump(res, open(out, 'w'), ensure_ascii=False)
            return res
        except Exception as ex:
            time.sleep(2 + attempt * 3)
    return None


def compare(res, gt):
    st = gt['subtask_times']
    T = lambda k, w: pd.to_datetime(st[k][w]) if st.get(k, {}).get(w) else None
    tab = {}
    for k in SUBS:
        a, b = T(k, 'start'), T(k, 'end')
        if a is not None and b is not None and 0 < (b - a).total_seconds() < 900:
            tab[k] = (a, (b - a).total_seconds())
    got = {s['sub']: s for s in res['segments']}
    common = [k for k in tab if k in got]
    if len(common) < 2:
        return {'n_tablet': len(tab), 'n_llm': len(got), 'n_common': len(common)}
    # fit offset: median over common of (llm start - tablet start seconds-since-form-start)
    fs = pd.to_datetime(gt['form_start'])
    diffs = [got[k]['start_s'] - (tab[k][0] - fs).total_seconds() for k in common]
    off = sorted(diffs)[len(diffs) // 2]
    errs = {k: round(got[k]['start_s'] - ((tab[k][0] - fs).total_seconds() + off), 1) for k in common}
    lens = {k: (round(got[k]['end_s'] - got[k]['start_s'], 1), round(tab[k][1], 1)) for k in common}
    within5 = sum(1 for v in errs.values() if abs(v) <= 5); within15 = sum(1 for v in errs.values() if abs(v) <= 15)
    timed = [k for k in common if k in ('letterid_urd', 'letterid_eng', 'idwrd_urd', 'idwrd_eng', 'pw_eng', 'orf_urd', 'orf_eng', 'blfluency')]
    len_err = [abs(lens[k][0] - lens[k][1]) for k in timed]
    return {'n_tablet': len(tab), 'n_llm': len(got), 'n_common': len(common), 'within5': within5, 'within15': within15,
            'mean_abs_start_err': round(sum(abs(v) for v in errs.values()) / len(errs), 1), 'timed_len_err': round(sum(len_err) / len(len_err), 1) if len_err else None,
            'errs': errs, 'lens': lens, 'cost': res.get('cost')}


if __name__ == '__main__':
    files = sorted(glob.glob('harness/soniox/*.json'))[:MAXF]
    files = [f for f in files if os.path.exists('harness/gt/' + os.path.basename(f))]
    print(MODEL, len(files), 'files', flush=True)
    rows = []
    with cf.ThreadPoolExecutor(4) as ex:
        for res in ex.map(label, files):
            if not res:
                continue
            gt = json.load(open('harness/gt/' + res['file']))
            c = compare(res, gt); c['file'] = res['file'][:20]; rows.append(c)
            print(res['file'][:20], {k: v for k, v in c.items() if k in ('n_tablet', 'n_llm', 'n_common', 'within5', 'within15', 'mean_abs_start_err', 'timed_len_err', 'cost')}, flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(f"harness/segmenter_llm_{MODEL.replace('/', '_')}.csv", index=False)
    if 'within5' in df:
        d = df.dropna(subset=['within5'])
        print(f"\nSUMMARY {MODEL}: files={len(d)} subtasks tablet={d.n_tablet.sum()} llm={d.n_llm.sum()} common={d.n_common.sum()} "
              f"start within 5s={d.within5.sum()} ({100 * d.within5.sum() / d.n_common.sum():.0f}%) within 15s={d.within15.sum()} ({100 * d.within15.sum() / d.n_common.sum():.0f}%) "
              f"mean|start err|={d.mean_abs_start_err.mean():.1f}s timed-len err={d.timed_len_err.mean():.1f}s cost/file=${d.cost.mean():.4f}")
