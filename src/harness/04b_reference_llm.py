"""Harness step 4b: reconstruct the reference stimuli with an LLM instead of positional voting.
Give Gemini 2.5 Pro up to 30 children's transcripts of the same subtask window and ask for the most likely original
printed stimulus in order (passage / word list / letter grid). Positional voting (04) degraded as N grew because it
seeds on the longest, insertion-heavy read; an LLM reads across children and recovers the text far better.
Output: harness/reference/<sub>.json  {ref:[...], source:'llm', n_children}
Run: uv run --with requests python harness/04b_reference_llm.py
"""
import os, json, glob, re, collections, requests, time, sys
sys.path.insert(0, 'harness')
import importlib.util
spec = importlib.util.spec_from_file_location('rr', 'harness/04_reference_reconstruct.py'); rr = importlib.util.module_from_spec(spec); spec.loader.exec_module(rr)

ROOT = "/Users/haroonyasin/Documents/Projects/April 2026/Rumi 10 April 2026"
KEY = [l.split('=', 1)[1].strip() for l in open(os.path.join(ROOT, '.env')) if l.startswith('NIETE_STAGING_OPENROUTER_API_KEY=')][-1]
MODEL = 'google/gemini-2.5-pro'
SEG_MODEL = 'google_gemini-2.5-pro'
DESC = {
    'orf_urd': 'a ~60–70-word Urdu story passage for Grade 2–3 (about Bilal going to the river Jhelum with his father)',
    'idwrd_urd': 'a list of ~50 common Urdu words (بچہ، دروازہ، پانی، کتاب …) read in order',
    'letterid_urd': 'a grid of 100 Urdu letters read by NAME in order (many repeats)',
    'orf_eng': 'a ~60-word English story passage for Grade 2–3 (about Imran, school, a plant)',
    'idwrd_eng': 'a list of ~50 common English words (boy, girl, school, book, teacher …) read in order',
    'pw_eng': 'a list of ~50 English pseudowords / nonsense words (e.g. lip, nape, dut …) read in order',
    'letterid_eng': 'a grid of 100 English letters read by name in order (many repeats)',
}
PROMPT = """You are reconstructing the ORIGINAL PRINTED STIMULUS of an EGRA subtask from transcripts of many different children reading it aloud in a noisy classroom (speech-to-text, so transcripts contain errors, omissions, repetitions and self-corrections). The stimulus is: {desc}.
Below are the children's transcripts, one per line. Reconstruct the most likely original text, in order, as a JSON array of tokens (one word / letter-name per token). Stop where the evidence runs out (later positions were reached by few children). Do not invent content that no child said. Return ONLY JSON: {{"ref": ["...", "..."], "notes": "..."}}"""


def collect():
    per = collections.defaultdict(list)
    for p in glob.glob(f'harness/segments_llm/{SEG_MODEL}__*.json'):
        r = json.load(open(p)); f = r['file']
        trp = 'harness/soniox/' + f
        if not os.path.exists(trp):
            continue
        tr_ur = json.load(open(trp))
        tr_en = json.load(open('harness/soniox_en/' + f)) if os.path.exists('harness/soniox_en/' + f) else None
        for s in r['segments']:
            sub = s['sub']
            if sub not in DESC or (s.get('confidence') or 0) < 0.7:
                continue
            tr = tr_en if sub.endswith('_eng') else tr_ur
            if tr is None:
                continue
            cw = rr.child_words(tr, s['start_s'], s['end_s'])
            if len(cw) >= 8:
                per[sub].append(' '.join(cw))
    return per


if __name__ == '__main__':
    per = collect()
    for sub, lines in per.items():
        lines = sorted(lines, key=len, reverse=True)[:30]
        body = PROMPT.format(desc=DESC[sub]) + '\n\n' + '\n'.join(f'{i + 1}. {l[:700]}' for i, l in enumerate(lines))
        for attempt in range(3):
            try:
                j = requests.post('https://openrouter.ai/api/v1/chat/completions', headers={'Authorization': f'Bearer {KEY}'},
                                  json={'model': MODEL, 'messages': [{'role': 'user', 'content': body}], 'max_tokens': 16000, 'temperature': 0}, timeout=300).json()
                c = j['choices'][0]['message']['content']; m = re.search(r'\{.*\}', c, re.S); out = json.loads(m.group(0))
                ref = [rr.clean(str(w)) for w in out['ref'] if rr.clean(str(w))]
                json.dump({'sub': sub, 'n_children': len(lines), 'ref': ref, 'source': 'llm', 'notes': out.get('notes', ''), 'cost': j.get('usage', {}).get('cost')}, open(f'harness/reference/{sub}.json', 'w'), ensure_ascii=False)
                open(f'harness/reference/{sub}.txt', 'w').write(' '.join(ref))
                print(f"{sub:12s} children={len(lines):3d} ref_len={len(ref):3d} cost=${j.get('usage', {}).get('cost', 0):.3f}  {' '.join(ref[:25])}")
                break
            except Exception as ex:
                print(sub, 'retry', attempt, str(ex)[:100]); time.sleep(3)
