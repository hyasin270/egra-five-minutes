"""Harness step 7: maths from speech. For each child, give a TEXT LLM the diarised transcript of the maths block
(STT timestamps) and ask it to list every question the enumerator asked, the child's final answer, and whether it
is correct, grouped by EGMA subtask. Compare per-subtask correct counts with the enumerator's numcorrect fields.
Run: uv run --with requests --with pandas python harness/07_maths_grade.py [model] [max_files]
"""
import os, sys, json, glob, re, time, requests, concurrent.futures as cf
import pandas as pd

ROOT = "/Users/haroonyasin/Documents/Projects/April 2026/Rumi 10 April 2026"
KEY = [l.split('=', 1)[1].strip() for l in open(os.path.join(ROOT, '.env')) if l.startswith('NIETE_STAGING_OPENROUTER_API_KEY=')][-1]
MODEL = sys.argv[1] if len(sys.argv) > 1 else 'google/gemini-2.5-pro'
MAXF = int(sys.argv[2]) if len(sys.argv) > 2 else 10000
SEG_MODEL = 'google_gemini-2.5-pro'
os.makedirs('harness/maths', exist_ok=True)
MSUBS = ['idnummag', 'numrep', 'blfluency', 'bleffcomp', 'wrdpblm', 'patterns']
ENUM_FIELD = {'idnummag': 'idnummag_numcorrect', 'numrep': 'numrep_numcorrect', 'bleffcomp': 'comp_numcorrect', 'wrdpblm': 'wrdpblm_numcorrect', 'patterns': 'patterns_numcorrect'}

PROMPT = """Below is a diarised, timestamped transcript (Urdu/English mix) of the MATHS block of an EGMA-style assessment: an enumerator asks a Grade 1-5 child questions orally; the child answers orally (sometimes after counting aloud). Subtasks in order: idnummag (identify numbers / which is bigger / order numbers, ~8 items), numrep (represent numbers: bundles of sticks, place value, how many hundreds, ~8 items), blfluency (rapid timed addition then subtraction, many short items), bleffcomp (computation like 25+7, 31-7, ~8 items), wrdpblm (word problems read aloud, ~8 items), patterns (shape/number patterns, ~8 items).
For every question you can identify, output: subtask, the question as asked (short), the child's FINAL answer (take the last number the child says; counting aloud before it is not the answer), the correct answer if you can determine it from the question, and whether the child's final answer is correct (true/false/unknown). If the child gives no audible answer, answer = null, correct = false.
Return ONLY JSON: {"items":[{"sub":"idnummag","q":"...","child":"16","correct_answer":"16","is_correct":true}, ...]}"""


def render_math(tr, s, e):
    toks = tr.get('tokens', [])
    turns = []
    for t in toks:
        ts, te, sp, tx = t.get('start_ms', 0) / 1000, t.get('end_ms', 0) / 1000, t.get('speaker'), t.get('text', '')
        if ts < s - 1 or te > e + 1:
            continue
        if turns and turns[-1]['spk'] == sp and ts - turns[-1]['e'] < 1.5:
            turns[-1]['text'] += tx; turns[-1]['e'] = te
        else:
            turns.append({'spk': sp, 's': ts, 'e': te, 'text': tx})
    return '\n'.join(f"[{tu['s']:.0f}-{tu['e']:.0f}] spk{tu['spk']}: {tu['text'].strip()[:500]}" for tu in turns)


def grade(segp):
    r = json.load(open(segp)); f = r['file']
    out = f"harness/maths/{MODEL.replace('/', '_')}__{f}"
    if os.path.exists(out):
        return json.load(open(out))
    segs = [s for s in r['segments'] if s['sub'] in MSUBS]
    if not segs:
        return None
    s0 = min(s['start_s'] for s in segs) - 5; e0 = max(s['end_s'] for s in segs) + 5
    tr = json.load(open('harness/soniox/' + f))
    text = render_math(tr, s0, e0)
    for attempt in range(3):
        try:
            resp = requests.post('https://openrouter.ai/api/v1/chat/completions', headers={'Authorization': f'Bearer {KEY}'},
                                 json={'model': MODEL, 'messages': [{'role': 'user', 'content': PROMPT + '\n\nTRANSCRIPT:\n' + text}], 'max_tokens': 16000, 'temperature': 0}, timeout=300).json()
            c = resp['choices'][0]['message']['content']; m = re.search(r'\{.*\}', c, re.S)
            res = {'file': f, 'model': MODEL, 'cost': resp.get('usage', {}).get('cost'), 'items': json.loads(m.group(0))['items']}
            json.dump(res, open(out, 'w'), ensure_ascii=False)
            return res
        except Exception:
            time.sleep(2 + 3 * attempt)
    return None


if __name__ == '__main__':
    files = sorted(glob.glob(f'harness/segments_llm/{SEG_MODEL}__*.json'))[:MAXF]
    print(MODEL, len(files), 'files', flush=True)
    rows = []
    with cf.ThreadPoolExecutor(4) as ex:
        for res in ex.map(grade, files):
            if not res:
                continue
            gt = json.load(open('harness/gt/' + res['file'])); sc = gt['scores']
            cnt = {}
            for it in res['items']:
                cnt.setdefault(it.get('sub'), [0, 0]); cnt[it['sub']][1] += 1
                if it.get('is_correct') is True: cnt[it['sub']][0] += 1
            row = {'file': res['file'][:20], 'cost': res.get('cost')}
            for sub, fld in ENUM_FIELD.items():
                row[f'{sub}_machine'] = cnt.get(sub, [None, 0])[0]; row[f'{sub}_n'] = cnt.get(sub, [0, 0])[1]; row[f'{sub}_enum'] = sc.get(fld)
            rows.append(row)
            print(res['file'][:20], {k: v for k, v in row.items() if k.endswith(('_machine', '_enum'))}, flush=True)
    df = pd.DataFrame(rows); df.to_csv(f"harness/maths_scores_{MODEL.replace('/', '_')}.csv", index=False)
    print('\nSUMMARY', MODEL, 'files', len(df), 'cost/file $%.3f' % df.cost.mean())
    for sub in ENUM_FIELD:
        d = df.dropna(subset=[f'{sub}_machine', f'{sub}_enum']).copy()
        if len(d) < 3: continue
        d[f'{sub}_enum'] = pd.to_numeric(d[f'{sub}_enum'])
        diff = d[f'{sub}_machine'] - d[f'{sub}_enum']
        print(f"  {sub:10s} n={len(d):3d} r={d[f'{sub}_machine'].corr(d[f'{sub}_enum']):.2f} MAE={diff.abs().mean():.2f} bias={diff.mean():+.2f} exact={100 * (diff == 0).mean():.0f}% within1={100 * (diff.abs() <= 1).mean():.0f}% items_found_mean={d[f'{sub}_n'].mean():.1f}")
