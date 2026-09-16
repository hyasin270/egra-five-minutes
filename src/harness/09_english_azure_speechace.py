"""Harness step 9: English passage + word list — Azure Pronunciation Assessment vs SpeechAce vs Soniox-diff,
all against the enumerator's counts and per-word flags.
- Azure: REST short-audio endpoint, locale en-IN (A/B en-US), Granularity=Word, EnableMiscue, on the 60-s window
  (short-audio cap is 60 s; we cut at 59 s from the child's first word).
- SpeechAce: /api/scoring/text/v9/json, dialect en-us, hard 30-s cap → the first 29 s only; the reference is truncated
  to the words the Soniox alignment shows the child reached by 29 s, and the enumerator comparison is restricted to
  those words.
Run: uv run --with requests --with pandas python harness/09_english_azure_speechace.py [max_files]
Outputs: harness/english/<engine>__<file>__<sub>.json and harness/english_results.csv
"""
import os, sys, json, glob, re, base64, subprocess, requests, time, urllib.parse
import pandas as pd
sys.path.insert(0, 'harness')
import importlib.util
spec = importlib.util.spec_from_file_location('rs', 'harness/06_reading_score.py'); rs = importlib.util.module_from_spec(spec); spec.loader.exec_module(rs)

ROOT = "/Users/haroonyasin/Documents/Projects/April 2026/Rumi 10 April 2026"
def env(path, key):
    for l in open(os.path.join(ROOT, path)):
        if l.startswith(key + '='):
            return l.split('=', 1)[1].strip().strip('"').strip("'")
AZ_KEY, AZ_REGION = env('02_Main Rumi Bot/.env', 'AZURE_SPEECH_KEY'), env('02_Main Rumi Bot/.env', 'AZURE_SPEECH_REGION')
SA_KEY, SA_EP = env('.env', 'SPEECHACE_API_KEY'), env('.env', 'SPEECHACE_ENDPOINT') or 'https://api5.speechace.com'
SEG_MODEL = 'google_gemini-2.5-pro'
MAXF = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
os.makedirs('harness/english', exist_ok=True)
SUBS = {'orf_eng': 'orf', 'idwrd_eng': 'idwrd'}


def cut(src, s, e, out):
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', f'{s:.2f}', '-to', f'{e:.2f}', '-i', src, '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', out], check=True)


def azure(wav, ref_text, locale):
    pa = base64.b64encode(json.dumps({'ReferenceText': ref_text, 'GradingSystem': 'HundredMark', 'Granularity': 'Word', 'Dimension': 'Comprehensive', 'EnableMiscue': True}).encode()).decode()
    r = requests.post(f'https://{AZ_REGION}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language={locale}&format=detailed',
                      headers={'Ocp-Apim-Subscription-Key': AZ_KEY, 'Pronunciation-Assessment': pa, 'Content-Type': 'audio/wav; codecs=audio/pcm; samplerate=16000', 'Accept': 'application/json'},
                      data=open(wav, 'rb').read(), timeout=120)
    return r.status_code, r.json() if r.headers.get('content-type', '').startswith('application/json') else {'raw': r.text[:300]}


def azure_words(j):
    """Per reference word: correct / mispronounced / omitted, from NBest[0].Words (ErrorType)."""
    try:
        ws = j['NBest'][0]['Words']
    except Exception:
        return None
    return [(w['Word'].lower(), w.get('PronunciationAssessment', {}).get('ErrorType', 'None'), w.get('PronunciationAssessment', {}).get('AccuracyScore')) for w in ws]


def speechace(wav, ref_text):
    r = requests.post(f'{SA_EP}/api/scoring/text/v9/json?key={urllib.parse.quote(SA_KEY, safe="")}&dialect=en-us&user_id=egra-harness',
                      files={'user_audio_file': open(wav, 'rb')}, data={'text': ref_text}, timeout=180)
    return r.status_code, r.json()


def speechace_words(j):
    try:
        ws = j['text_score']['word_score_list']
    except Exception:
        return None
    return [(w['word'].lower(), w.get('quality_score')) for w in ws]


if __name__ == '__main__':
    refs = {s: json.load(open(f'harness/reference/{s}.json'))['ref'] for s in SUBS if os.path.exists(f'harness/reference/{s}.json')}
    print('refs', {k: len(v) for k, v in refs.items()}, 'azure region', AZ_REGION)
    rows = []
    files = sorted(glob.glob(f'harness/segments_llm/{SEG_MODEL}__*.json'))[:MAXF]
    for p in files:
        r = json.load(open(p)); f = r['file']
        enp, gtp = 'harness/whisper_en/' + f, 'harness/gt/' + f
        if not (os.path.exists(enp) and os.path.exists(gtp)):
            continue
        tr_en = json.load(open(enp)); gt = json.load(open(gtp)); sc = gt['scores']; src = 'audio/' + f.replace('.json', '')
        for s in r['segments']:
            sub = s['sub']
            if sub not in refs:
                continue
            toks = rs.child_tokens(tr_en, s['start_s'], s['end_s']); wt = rs.words_with_time(toks)
            if not wt:
                continue
            t0 = wt[0][1]
            hyp60 = [w for w, t in wt if t - t0 <= 60.5]; hyp29 = [w for w, t in wt if t - t0 <= 29.0]
            st60, _ = rs.align(refs[sub], hyp60); att60 = rs.last_attempted(st60)
            st29, _ = rs.align(refs[sub], hyp29); att29 = rs.last_attempted(st29)
            ref60 = refs[sub][:max(5, min(att60, len(hyp60) + 3))]; ref29 = refs[sub][:max(5, min(att29, len(hyp29) + 3))]
            flags = gt['items'].get(sub) or []
            pre = SUBS[sub]
            e_corr = sc.get(f'{pre}_60s_correct_eng') or sc.get(f'{pre}_reading_correct_eng'); e_att = sc.get(f'{pre}_60s_attempted_eng') or sc.get(f'{pre}_reading_attempted_eng')
            base = dict(file=f[:20], sub=sub, enum_correct=e_corr, enum_attempted=e_att, soniox_correct=sum(1 for x in st60[:att60] if x == 'correct'), soniox_attempted=att60)
            # ---- Azure (60 s) en-IN and en-US
            wav60 = f'harness/english/_tmp60.wav'; cut(src, t0 - 0.3, t0 + 59.0, wav60)
            for loc in (('en-IN', 'en-US') if os.environ.get('AZURE_OK') == '1' else ()):
                outp = f"harness/english/azure-{loc}__{f}__{sub}.json"
                if os.path.exists(outp):
                    j = json.load(open(outp))
                else:
                    code, j = azure(wav60, ' '.join(ref60), loc); j['_status'] = code; json.dump(j, open(outp, 'w')); time.sleep(0.3)
                aw = azure_words(j)
                if aw:
                    n_ok = sum(1 for w, et, a in aw if et == 'None'); n_att = sum(1 for w, et, a in aw if et != 'Omission')
                    agree = None
                    if flags:
                        pairs = [(int(et != 'None'), int(flags[i])) for i, (w, et, a) in enumerate(aw) if i < len(flags) and flags[i] is not None]
                        if pairs:
                            agree = sum(1 for m, e in pairs if m == e) / len(pairs)
                    rows.append(dict(base, engine=f'azure-{loc}', machine_correct=n_ok, machine_attempted=n_att, item_agree=agree, n_items=len(aw), status=j.get('_status')))
                else:
                    rows.append(dict(base, engine=f'azure-{loc}', machine_correct=None, machine_attempted=None, item_agree=None, n_items=0, status=j.get('_status'), err=str(j)[:120]))
            # ---- SpeechAce (first 29 s)
            outp = f"harness/english/speechace__{f}__{sub}.json"
            wav29 = f'harness/english/_tmp29.wav'; cut(src, t0 - 0.3, t0 + 28.7, wav29)
            if os.path.exists(outp):
                j = json.load(open(outp))
            else:
                try:
                    code, j = speechace(wav29, ' '.join(ref29)); j['_status'] = code
                except Exception as ex:
                    j = {'_status': 'exc', 'err': str(ex)[:200]}
                json.dump(j, open(outp, 'w')); time.sleep(0.3)
            sw = speechace_words(j)
            if sw:
                n_ok = sum(1 for w, q in sw if (q or 0) >= 60)
                e29_corr = sum(1 for i in range(min(att29, len(flags))) if flags[i] == 0) if flags else None
                agree = None
                if flags:
                    pairs = [(int((q or 0) < 60), int(flags[i])) for i, (w, q) in enumerate(sw) if i < len(flags) and flags[i] is not None]
                    if pairs:
                        agree = sum(1 for m, e in pairs if m == e) / len(pairs)
                rows.append(dict(base, engine='speechace-29s', machine_correct=n_ok, machine_attempted=len(sw), item_agree=agree, n_items=len(sw), status=j.get('_status'), enum_correct_29s=e29_corr, soniox_correct_29s=sum(1 for x in st29[:att29] if x == 'correct')))
            else:
                rows.append(dict(base, engine='speechace-29s', machine_correct=None, machine_attempted=None, item_agree=None, n_items=0, status=j.get('_status'), err=str(j)[:160]))
        print(f[:20], 'done', flush=True)
    df = pd.DataFrame(rows); df.to_csv('harness/english_results.csv', index=False)
    for (eng, sub), d in df.groupby(['engine', 'sub']):
        ok = d.dropna(subset=['machine_correct', 'enum_correct']).copy()
        if len(ok) < 3:
            print(eng, sub, 'n', len(ok), 'statuses', d.status.value_counts().to_dict()); continue
        ok['enum_correct'] = pd.to_numeric(ok.enum_correct)
        ref_col = 'enum_correct_29s' if eng.startswith('speechace') and 'enum_correct_29s' in ok else 'enum_correct'
        ok[ref_col] = pd.to_numeric(ok[ref_col])
        diff = ok.machine_correct - ok[ref_col]
        print(f"{eng:14s} {sub:10s} n={len(ok):3d} correct-count r={ok.machine_correct.corr(ok[ref_col]):.2f} MAE={diff.abs().mean():.1f} bias={diff.mean():+.1f} within±3={100 * (diff.abs() <= 3).mean():.0f}% | per-item agreement={ok.item_agree.mean():.2f}")
    d = df[df.engine == 'azure-en-IN'].dropna(subset=['soniox_correct', 'enum_correct']).copy(); d['enum_correct'] = pd.to_numeric(d.enum_correct)
    for sub, dd in d.groupby('sub'):
        diff = dd.soniox_correct - dd.enum_correct
        print(f"{'soniox-diff':14s} {sub:10s} n={len(dd):3d} correct-count r={dd.soniox_correct.corr(dd.enum_correct):.2f} MAE={diff.abs().mean():.1f} bias={diff.mean():+.1f} within±3={100 * (diff.abs() <= 3).mean():.0f}%")
