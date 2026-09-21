"""Harness step 8: second Soniox pass on the ENGLISH block only, language hint 'en' only.
Finding from step 4: with hints ['ur','en'] + language identification, Soniox writes the child's accented English
in Urdu script (transliteration), which makes English scoring impossible. So: cut the English block
(letterid_eng instruction → rdcomp_eng end, from the LLM-labelled segments) and transcribe it again as English.
Output: harness/soniox_en/<file>.json (tokens with start_ms offset back to the full-recording clock).
Run: uv run --with requests python harness/08_soniox_english_pass.py [max_files]
"""
import os, sys, json, glob, subprocess, requests, time, concurrent.futures as cf

ROOT = "/Users/haroonyasin/Documents/Projects/April 2026/Rumi 10 April 2026"
KEY = [l.split('=', 1)[1].strip() for l in open(os.path.join(ROOT, '02_Main Rumi Bot/.env')) if l.startswith('SONIOX_API_KEY=')][-1]
H = {'Authorization': f'Bearer {KEY}'}
SEG_MODEL = 'google_gemini-2.5-pro'
MAXF = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
os.makedirs('harness/soniox_en', exist_ok=True)
ENG = ['listcomp_eng', 'letterid_eng', 'pw_eng', 'idwrd_eng', 'orf_eng', 'rdcomp_eng']


def one(segp):
    r = json.load(open(segp)); f = r['file']
    out = f'harness/soniox_en/{f}'
    if os.path.exists(out):
        return f, 'cached'
    segs = [s for s in r['segments'] if s['sub'] in ENG]
    if not segs:
        return f, 'no-english-segments'
    s0 = max(0, min(s.get('instr_s', s['start_s']) for s in segs) - 3); e0 = max(s['end_s'] for s in segs) + 3
    src = 'audio/' + f.replace('.json', ''); wav = f'harness/soniox_en/{f}.wav'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', str(s0), '-to', str(e0), '-i', src, '-ar', '16000', '-ac', '1', wav], check=True)
    try:
        fl = requests.post('https://api.soniox.com/v1/files', headers=H, files={'file': open(wav, 'rb')}, timeout=300).json(); fid = fl['id']
        t = requests.post('https://api.soniox.com/v1/transcriptions', headers=H, json={'file_id': fid, 'model': 'stt-async-v3', 'language_hints': ['en'], 'enable_language_identification': False,
                                                                                    'enable_speaker_diarization': True, 'speaker_diarization_config': {'min_speakers': 2, 'max_speakers': 4}}, timeout=60).json(); tid = t['id']
        while True:
            s = requests.get(f'https://api.soniox.com/v1/transcriptions/{tid}', headers=H, timeout=60).json()
            if s['status'] in ('completed', 'error'):
                break
            time.sleep(3)
        if s['status'] != 'completed':
            return f, 'error'
        tr = requests.get(f'https://api.soniox.com/v1/transcriptions/{tid}/transcript', headers=H, timeout=120).json()
        for tk in tr.get('tokens', []):
            tk['start_ms'] = tk.get('start_ms', 0) + int(s0 * 1000); tk['end_ms'] = tk.get('end_ms', 0) + int(s0 * 1000)
        tr['window'] = [s0, e0]
        json.dump(tr, open(out, 'w'), ensure_ascii=False)
        requests.delete(f'https://api.soniox.com/v1/transcriptions/{tid}', headers=H, timeout=30); requests.delete(f'https://api.soniox.com/v1/files/{fid}', headers=H, timeout=30)
        return f, f"ok:{len(tr.get('tokens', []))}tok window={e0 - s0:.0f}s"
    finally:
        if os.path.exists(wav):
            os.remove(wav)


if __name__ == '__main__':
    files = sorted(glob.glob(f'harness/segments_llm/{SEG_MODEL}__*.json'))[:MAXF]
    print(len(files), 'files', flush=True)
    with cf.ThreadPoolExecutor(4) as ex:
        for f, st in ex.map(one, files):
            print(f[:20], st, flush=True)
    print('EN_PASS_DONE', flush=True)
