"""Harness step 8b: English block via OpenAI whisper-1 with language forced to 'en' + word timestamps.
Why: Soniox with language_hints=['en'] still returned the child's accented English letter names and words in
Devanagari/Urdu script (hints are hints). whisper-1 honours `language` strictly and returns word timestamps.
Output: harness/whisper_en/<file>.json in the same token shape as the Soniox files (start_ms/end_ms absolute,
speaker=None) so the scorers can consume it unchanged.
Run: uv run --with requests python harness/08b_whisper_english_pass.py [max_files]
"""
import os, sys, json, glob, subprocess, requests, time, concurrent.futures as cf

ROOT = "/Users/haroonyasin/Documents/Projects/April 2026/Rumi 10 April 2026"
KEY = [l.split('=', 1)[1].strip() for l in open(os.path.join(ROOT, '02_Main Rumi Bot/.env')) if l.startswith('OPENAI_API_KEY=')][-1]
SEG_MODEL = 'google_gemini-2.5-pro'
MAXF = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
os.makedirs('harness/whisper_en', exist_ok=True)
ENG = ['letterid_eng', 'pw_eng', 'idwrd_eng', 'orf_eng']


def one(segp):
    r = json.load(open(segp)); f = r['file']
    out = f'harness/whisper_en/{f}'
    if os.path.exists(out):
        return f, 'cached'
    segs = [s for s in r['segments'] if s['sub'] in ENG]
    if not segs:
        return f, 'no-english-segments'
    src = 'audio/' + f.replace('.json', '')
    tokens = []; cost_min = 0
    for s in segs:  # one call per subtask window (≤ ~2 min each) so the prompt can carry the stimulus type
        s0, e0 = max(0, s['start_s'] - 1.0), s['end_s'] + 1.0
        wav = f"harness/whisper_en/_{f}_{s['sub']}.mp3"
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', f'{s0:.2f}', '-to', f'{e0:.2f}', '-i', src, '-ar', '16000', '-ac', '1', '-b:a', '64k', wav], check=True)
        prompt = {'letterid_eng': 'A child names English letters one by one: L, I, H, R, S, Y, E, O, N, T.', 'pw_eng': 'A child reads made-up nonsense words one by one: maz, zaj, ver, lut, eaf.',
                  'idwrd_eng': 'A child reads English words one by one: boy, girl, school, book, pen, bag, teacher.', 'orf_eng': 'A child reads a short English story about Imran and a plant aloud.'}[s['sub']]
        for attempt in range(3):
            try:
                resp = requests.post('https://api.openai.com/v1/audio/transcriptions', headers={'Authorization': f'Bearer {KEY}'},
                                     files={'file': open(wav, 'rb')}, data={'model': 'whisper-1', 'language': 'en', 'response_format': 'verbose_json', 'timestamp_granularities[]': 'word', 'prompt': prompt, 'temperature': 0}, timeout=300)
                j = resp.json()
                if 'words' not in j:
                    raise RuntimeError(str(j)[:200])
                for w in j['words']:
                    tokens.append({'text': ' ' + w['word'], 'start_ms': int((s0 + w['start']) * 1000), 'end_ms': int((s0 + w['end']) * 1000), 'speaker': None, 'language': 'en', 'sub': s['sub']})
                cost_min += (e0 - s0) / 60
                break
            except Exception as ex:
                time.sleep(2 + 3 * attempt)
                if attempt == 2:
                    return f, 'error:' + str(ex)[:80]
        os.remove(wav)
    json.dump({'tokens': tokens, 'engine': 'whisper-1', 'minutes': round(cost_min, 2)}, open(out, 'w'), ensure_ascii=False)
    return f, f'ok:{len(tokens)}words {cost_min:.1f}min'


if __name__ == '__main__':
    files = sorted(glob.glob(f'harness/segments_llm/{SEG_MODEL}__*.json'))[:MAXF]
    print(len(files), 'files', flush=True)
    with cf.ThreadPoolExecutor(4) as ex:
        for f, st in ex.map(one, files):
            print(f[:20], st, flush=True)
    print('WHISPER_EN_DONE', flush=True)
