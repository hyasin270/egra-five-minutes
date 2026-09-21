"""Harness round 2, step 10: score the 60-second reading windows with the models we recommended but had not tested.
Two arms, same prompt, same reference text, same children:
  - AUDIO arm: the 60-s clip itself goes to an audio-capable LLM via OpenRouter (Gemini 2.5/3.x, gpt-audio, mimo, voxtral, ...)
  - TEXT arm:  the STT transcript of the same window goes to a text LLM (gpt-5-mini, claude-sonnet-5, ...) — does an LLM
               judge per-word verdicts better than plain Levenshtein alignment does?
Each call returns JSON: per reference word {correct|wrong|skipped} + words_correct. Compared with the enumerator's count and
per-word flags; the human floor and the Levenshtein baseline sit beside every number.
Run: uv run --with requests --with pandas python harness/10_window_scorers.py <arm:audio|text> <model> [n_children]
Outputs: harness/windows/<arm>__<model>__<file>__<sub>.json and harness/window_scores.csv (appended)
"""
import os, sys, json, glob, re, base64, subprocess, requests, time, random
import pandas as pd
sys.path.insert(0, 'harness')
import importlib.util
spec = importlib.util.spec_from_file_location('rs', 'harness/06_reading_score.py'); rs = importlib.util.module_from_spec(spec); spec.loader.exec_module(rs)

ROOT = "/Users/haroonyasin/Documents/Projects/April 2026/Rumi 10 April 2026"
KEY = [l.split('=', 1)[1].strip() for l in open(os.path.join(ROOT, '.env')) if l.startswith('NIETE_STAGING_OPENROUTER_API_KEY=')][-1]
ARM, MODEL = sys.argv[1], sys.argv[2]
N = int(sys.argv[3]) if len(sys.argv) > 3 else 40
SEG_MODEL = 'google_gemini-2.5-pro'
SUBS = {'orf_urd': ('Urdu', 'orf'), 'orf_eng': ('English', 'orf'), 'idwrd_urd': ('Urdu', 'idwrd')}
os.makedirs('harness/windows', exist_ok=True)
random.seed(7)

PROMPT = """A child in a Pakistani government school (grade 1-5) is reading aloud from a printed {lang} text for 60 seconds. The exact printed text, word by word, is:
{ref}
Judge every word of the printed text in order. For each word say whether the child read it CORRECTLY (an acceptable pronunciation of that word), read it WRONG (said a different word or a mispronunciation that changes the word), or SKIPPED it (never attempted, including everything after the child stopped). Self-corrections count as correct. Do not invent words the child did not say. Return ONLY JSON:
{{"words":[{{"i":1,"w":"<word>","v":"correct|wrong|skipped"}}, ...], "words_correct": <int>, "words_attempted": <int>, "notes":"<one line>"}}"""


def window(f, s):
    """60-s clip from the child's first word (whisper for English, Soniox for Urdu), like 06 does."""
    trp = 'harness/whisper_en/' + f if s['sub'].endswith('_eng') else 'harness/soniox/' + f
    if not os.path.exists(trp):
        return None, None
    tr = json.load(open(trp))
    wt = rs.words_with_time(rs.child_tokens(tr, s['start_s'], s['end_s']))
    if not wt:
        return None, None
    t0 = wt[0][1]
    return t0, [w for w, t in wt if t - t0 <= 60.5]


def call(messages, max_tokens=6000):
    for attempt in range(3):
        try:
            r = requests.post('https://openrouter.ai/api/v1/chat/completions', headers={'Authorization': f'Bearer {KEY}'},
                              json={'model': MODEL, 'messages': messages, 'max_tokens': max_tokens, **({} if 'voxtral' in MODEL else {'temperature': 0})}, timeout=300)
            j = r.json()
            if 'choices' not in j:
                raise RuntimeError(str(j)[:200])
            c = j['choices'][0]['message']['content'] or ''
            m = re.search(r'\{.*\}', c, re.S)
            return json.loads(m.group(0)), j.get('usage', {}).get('cost'), None
        except Exception as ex:
            err = str(ex)[:160]; time.sleep(2 + 3 * attempt)
    return None, None, err


if __name__ == '__main__':
    refs = {s: json.load(open(f'harness/reference/{s}.json'))['ref'] for s in SUBS}
    files = sorted(glob.glob(f'harness/segments_llm/{SEG_MODEL}__*.json'))
    random.shuffle(files); files = files[:N]
    rows = []; spent = 0.0
    for p in files:
        r = json.load(open(p)); f = r['file']; gtp = 'harness/gt/' + f
        if not os.path.exists(gtp):
            continue
        gt = json.load(open(gtp)); sc = gt['scores']; src = 'audio/' + f.replace('.json', '')
        for s in r['segments']:
            sub = s['sub']
            if sub not in SUBS or (s.get('confidence') or 0) < 0.7:
                continue
            lang, pre = SUBS[sub]; ref = refs[sub]
            t0, hyp = window(f, s)
            if t0 is None:
                continue
            out = f"harness/windows/{ARM}__{MODEL.replace('/', '_')}__{f}__{sub}.json"
            if os.path.exists(out):
                res = json.load(open(out))
            elif os.environ.get('CACHE_ONLY'):
                continue
            else:
                prompt = PROMPT.format(lang=lang, ref=' '.join(f'{i + 1}:{w}' for i, w in enumerate(ref)))
                if ARM == 'audio':
                    mp3 = 'harness/windows/_tmp.mp3'
                    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', f'{max(0, t0 - 0.5):.2f}', '-to', f'{t0 + 61:.2f}', '-i', src, '-ar', '16000', '-ac', '1', '-b:a', '48k', mp3], check=True)
                    b64 = base64.b64encode(open(mp3, 'rb').read()).decode()
                    msgs = [{'role': 'user', 'content': [{'type': 'text', 'text': prompt}, {'type': 'input_audio', 'input_audio': {'data': b64, 'format': 'mp3'}}]}]
                else:
                    msgs = [{'role': 'user', 'content': prompt + '\n\nSPEECH-TO-TEXT TRANSCRIPT of what the child said in those 60 seconds (may contain recognition errors):\n' + ' '.join(hyp)}]
                j, cost, err = call(msgs)
                res = {'file': f, 'sub': sub, 'arm': ARM, 'model': MODEL, 'cost': cost, 'error': err, 'result': j}
                json.dump(res, open(out, 'w'), ensure_ascii=False)
            spent += res.get('cost') or 0
            j = res.get('result')
            if not j:
                rows.append(dict(arm=ARM, model=MODEL, file=f[:20], sub=sub, error=(res.get('error') or 'no-json')[:80])); continue
            verd = [w.get('v') for w in j.get('words', [])]
            flags = gt['items'].get(sub) or []
            att = len([v for v in verd if v != 'skipped']); att = max((i + 1 for i, v in enumerate(verd) if v != 'skipped'), default=0)
            m_corr = sum(1 for v in verd[:att] if v == 'correct')
            lang_k = 'urd' if sub.endswith('urd') else 'eng'
            e_corr = sc.get(f'{pre}_60s_correct_{lang_k}') or sc.get(f'{pre}_reading_correct_{lang_k}')
            e_corr_att = sc.get(f'{pre}_60s_attempted_{lang_k}') or sc.get(f'{pre}_reading_attempted_{lang_k}')
            reach = min(att, int(float(e_corr_att)) if e_corr_att not in (None, '') else att, len(flags))
            pairs = [(int(verd[i] != 'correct'), int(flags[i])) for i in range(reach) if flags[i] is not None]
            tp = sum(1 for m, e in pairs if m and e); fp = sum(1 for m, e in pairs if m and not e); fn = sum(1 for m, e in pairs if e and not m)
            # Levenshtein baseline on the same window
            st, _ = rs.align(ref, hyp); att_b = rs.last_attempted(st); b_corr = sum(1 for x in st[:att_b] if x == 'correct')
            rows.append(dict(arm=ARM, model=MODEL, file=f[:20], sub=sub, machine_correct=m_corr, machine_attempted=att, enum_correct=e_corr, baseline_correct=b_corr,
                             n_pairs=len(pairs), tp=tp, fp=fp, fn=fn, cost=res.get('cost')))
        print(f[:20], f'spent ${spent:.2f}', flush=True)
    df = pd.DataFrame(rows)
    csvp = 'harness/window_scores.csv'
    if os.path.exists(csvp) and os.path.getsize(csvp) > 10:
        old = pd.read_csv(csvp); old = old[~((old.arm == ARM) & (old.model == MODEL))]; df = pd.concat([old, df])
    df.to_csv(csvp, index=False)
    d = df[(df.arm == ARM) & (df.model == MODEL)].dropna(subset=['machine_correct', 'enum_correct']).copy()
    print(f'\nSUMMARY {ARM} {MODEL}: windows={len(d)} spent=${spent:.2f}')
    for sub, g in d.groupby('sub'):
        g = g.assign(enum_correct=pd.to_numeric(g.enum_correct)); diff = g.machine_correct - g.enum_correct; bd_ = g.baseline_correct - g.enum_correct
        prec = g.tp.sum() / max(1, g.tp.sum() + g.fp.sum()); rec = g.tp.sum() / max(1, g.tp.sum() + g.fn.sum())
        print(f"  {sub:10s} n={len(g):3d} count r={g.machine_correct.corr(g.enum_correct):.2f} MAE={diff.abs().mean():.1f} bias={diff.mean():+.1f} within±5={100 * (diff.abs() <= 5).mean():.0f}% | per-word precision={prec:.2f} recall={rec:.2f} | Levenshtein baseline on same windows: r={g.baseline_correct.corr(g.enum_correct):.2f} MAE={bd_.abs().mean():.1f}")
