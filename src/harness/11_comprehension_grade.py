"""Harness round 2, step 11: grade the Urdu reading-comprehension answers with text LLMs.
Input per child: the reconstructed Urdu passage + the diarised transcript of the rdcomp_urd window (enumerator's questions
and the child's spoken answers). The LLM returns one verdict per question. Compared with the enumerator's
rdcomp_numcorrect_urd (count) — the per-item flag semantics in the export are not documented, so counts only.
Run: uv run --with requests --with pandas python harness/11_comprehension_grade.py <model> [n_children]
"""
import os, sys, json, glob, re, requests, time, random
import pandas as pd

ROOT = "/Users/haroonyasin/Documents/Projects/April 2026/Rumi 10 April 2026"
KEY = [l.split('=', 1)[1].strip() for l in open(os.path.join(ROOT, '.env')) if l.startswith('NIETE_STAGING_OPENROUTER_API_KEY=')][-1]
MODEL = sys.argv[1]; N = int(sys.argv[2]) if len(sys.argv) > 2 else 100
SEG_MODEL = 'google_gemini-2.5-pro'
os.makedirs('harness/comprehension', exist_ok=True)
random.seed(11)
PROMPT = """You are marking an oral reading-comprehension test in Urdu for a grade 1-5 child in Pakistan. The child has just read this passage aloud:
{passage}
Below is a timestamped, diarised transcript of the enumerator asking up to 6 questions about the passage (4 literal, 2 inferential) and the child answering. Speech-to-text errors are possible; judge the meaning. An answer is CORRECT if it conveys the right information from the passage in any language or wording; WRONG if it is incorrect, off-topic, or the child says they do not know; NO_ANSWER if no audible answer. Mark each question in order.
Return ONLY JSON: {{"questions":[{{"n":1,"q":"<question as asked>","answer":"<child's answer>","verdict":"correct|wrong|no_answer"}}, ...], "num_correct": <int>}}
TRANSCRIPT:
{transcript}"""


def render(tr, s, e):
    turns = []
    for t in tr.get('tokens', []):
        ts, te, sp, tx = t.get('start_ms', 0) / 1000, t.get('end_ms', 0) / 1000, t.get('speaker'), t.get('text', '')
        if ts < s - 1 or te > e + 1:
            continue
        if turns and turns[-1]['spk'] == sp and ts - turns[-1]['e'] < 1.5:
            turns[-1]['text'] += tx; turns[-1]['e'] = te
        else:
            turns.append({'spk': sp, 's': ts, 'e': te, 'text': tx})
    return '\n'.join(f"[{tu['s']:.0f}s] spk{tu['spk']}: {tu['text'].strip()[:400]}" for tu in turns)


if __name__ == '__main__':
    passage = ' '.join(json.load(open('harness/reference/orf_urd.json'))['ref'])
    files = sorted(glob.glob(f'harness/segments_llm/{SEG_MODEL}__*.json')); random.shuffle(files); files = files[:N]
    rows = []; spent = 0.0
    for p in files:
        r = json.load(open(p)); f = r['file']; gtp = 'harness/gt/' + f
        if not os.path.exists(gtp):
            continue
        gt = json.load(open(gtp)); sc = gt['scores']
        seg = next((s for s in r['segments'] if s['sub'] == 'rdcomp_urd'), None)
        e_num = sc.get('rdcomp_numcorrect_urd')
        if not seg or e_num in (None, ''):
            continue
        out = f"harness/comprehension/{MODEL.replace('/', '_')}__{f}"
        if os.path.exists(out):
            res = json.load(open(out))
        else:
            tr = json.load(open('harness/soniox/' + f))
            text = render(tr, seg['start_s'], seg['end_s'] + 5)
            res = {'file': f, 'model': MODEL, 'cost': None, 'result': None, 'error': None}
            for attempt in range(3):
                try:
                    j = requests.post('https://openrouter.ai/api/v1/chat/completions', headers={'Authorization': f'Bearer {KEY}'},
                                      json={'model': MODEL, 'messages': [{'role': 'user', 'content': PROMPT.format(passage=passage, transcript=text)}], 'max_tokens': 3000, 'temperature': 0}, timeout=180).json()
                    c = j['choices'][0]['message']['content']; m = re.search(r'\{.*\}', c, re.S)
                    res['result'] = json.loads(m.group(0)); res['cost'] = j.get('usage', {}).get('cost'); break
                except Exception as ex:
                    res['error'] = str(ex)[:160]; time.sleep(2 + 3 * attempt)
            json.dump(res, open(out, 'w'), ensure_ascii=False)
        spent += res.get('cost') or 0
        if res.get('result'):
            qs = res['result'].get('questions', [])
            rows.append(dict(model=MODEL, file=f[:20], machine=sum(1 for q in qs if q.get('verdict') == 'correct'), n_q=len(qs), enum=float(e_num), cost=res.get('cost')))
    df = pd.DataFrame(rows)
    csvp = 'harness/comprehension_scores.csv'
    if os.path.exists(csvp):
        old = pd.read_csv(csvp); old = old[old.model != MODEL]; df = pd.concat([old, df])
    df.to_csv(csvp, index=False)
    d = df[df.model == MODEL]
    if len(d):
        diff = d.machine - d.enum
        print(f"SUMMARY {MODEL}: n={len(d)} spent=${spent:.2f} r={d.machine.corr(d.enum):.2f} MAE={diff.abs().mean():.2f} bias={diff.mean():+.2f} exact={100 * (diff == 0).mean():.0f}% within1={100 * (diff.abs() <= 1).mean():.0f}% questions_found_mean={d.n_q.mean():.1f} (enumerator asks 6)")
