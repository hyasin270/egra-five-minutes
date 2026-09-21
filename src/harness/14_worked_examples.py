"""Harness step 14: worked examples — one page per scored window showing every artefact behind the score.
For each chosen window: the printed text the child was supposed to read, the 60-s clip (uploaded to a Drive folder shared
with the Taleemabad domain; child audio never goes on the public site), the speech-to-text transcript, the enumerator's
per-word marks, the round-1 alignment verdicts, every model's per-word verdicts, and the resulting counts side by side.
Output: harness/examples/*.html + index.html (copied into the site by build_site.py).
Run: uv run --with pandas --with google-api-python-client --with google-auth python harness/14_worked_examples.py [n_per_subtask]
"""
import os, sys, json, glob, html, subprocess, random, io
import pandas as pd
sys.path.insert(0, 'harness')
import importlib.util
spec = importlib.util.spec_from_file_location('rs', 'harness/06_reading_score.py'); rs = importlib.util.module_from_spec(spec); spec.loader.exec_module(rs)

ROOT = "/Users/haroonyasin/Documents/Projects/April 2026/Rumi 10 April 2026"
N_PER = int(sys.argv[1]) if len(sys.argv) > 1 else 4
OUT = 'harness/examples'; os.makedirs(OUT, exist_ok=True); os.makedirs('harness/examples/_clips', exist_ok=True)
SUBS = {'orf_urd': ('Urdu story (60 s)', 'orf', 'urd'), 'orf_eng': ('English story (60 s)', 'orf', 'eng'), 'idwrd_urd': ('Urdu word list (60 s)', 'idwrd', 'urd')}
SHORT = {'google/gemini-3.1-pro-preview': 'Gemini 3.1 Pro · audio', 'google/gemini-3.8-flash': 'Gemini 3.8 Flash · audio', 'google/gemini-3.5-flash-lite': 'Gemini 3.5 Flash-Lite · audio', 'google/gemini-2.5-flash': 'Gemini 2.5 Flash · audio',
         'openai/gpt-audio': 'GPT audio · audio', 'openai/gpt-audio-mini': 'GPT audio mini · audio', 'xiaomi/mimo-v2.5': 'MiMo 2.5 · audio', 'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free': 'Nemotron omni · audio', 'mistralai/voxtral-small-24b-2507': 'Voxtral small · audio',
         'anthropic/claude-sonnet-5': 'Claude Sonnet 5 · transcript', 'openai/gpt-5-mini': 'GPT-5 mini · transcript', 'google/gemini-3-flash-preview': 'Gemini 3 Flash · transcript', 'deepseek/deepseek-v3.2': 'DeepSeek 3.2 · transcript'}
ORDER = list(SHORT)
random.seed(21)

# ---- Drive folder for the clips (rumi@hellorumi.ai's Drive, shared with the domain)
def drive_client():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    sa = os.environ.get('GOOGLE_SERVICE_ACCOUNT_PATH') or 'keys/google_service_account.json'
    if not os.path.isabs(sa):
        sa = os.path.join(ROOT, sa)
    creds = service_account.Credentials.from_service_account_file(sa, scopes=['https://www.googleapis.com/auth/drive'], subject='rumi@hellorumi.ai')
    return build('drive', 'v3', credentials=creds)

def ensure_folder(drive):
    q = "name='EGRA harness worked examples (child clips)' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    r = drive.files().list(q=q, fields='files(id,webViewLink)').execute()['files']
    if r:
        return r[0]['id'], r[0]['webViewLink']
    f = drive.files().create(body={'name': 'EGRA harness worked examples (child clips)', 'mimeType': 'application/vnd.google-apps.folder'}, fields='id,webViewLink').execute()
    for dom in ('taleemabad.com', 'hellorumi.ai', 'niete.edu.pk'):
        try:
            drive.permissions().create(fileId=f['id'], body={'type': 'domain', 'role': 'reader', 'domain': dom}, fields='id').execute()
        except Exception as ex:
            print('permission', dom, str(ex)[:80])
    return f['id'], f['webViewLink']

def upload(drive, folder_id, path, name):
    from googleapiclient.http import MediaFileUpload
    r = drive.files().list(q=f"name='{name}' and '{folder_id}' in parents and trashed=false", fields='files(id,webViewLink)').execute()['files']
    if r:
        return r[0]['webViewLink']
    f = drive.files().create(body={'name': name, 'parents': [folder_id]}, media_body=MediaFileUpload(path, mimetype='audio/mpeg'), fields='id,webViewLink').execute()
    return f['webViewLink']

# ---- helpers
def chip(word, v):
    cls = {'correct': 'ok', 'wrong': 'bad', 'sub': 'bad', 'omit': 'skip', 'skipped': 'skip', None: 'na'}.get(v, 'na')
    return f'<span class="w {cls}">{html.escape(str(word))}</span>'

def row_html(label, ref, verdicts, note='', lang='urd'):
    cells = ''.join(chip(ref[i], verdicts[i] if i < len(verdicts) else None) for i in range(len(ref)))
    return f'<div class="vrow"><div class="lab">{html.escape(label)}</div><div class="chips{" ltr" if lang == "eng" else ""}">{cells}</div>{("<div class=note>" + html.escape(note) + "</div>") if note else ""}</div>'

HOWTO = '''<div class="box"><strong>How to read this page.</strong> Section 1 is the printed text the child had in front of them, numbered in reading order. Section 2 is the 60-second clip, timed from the child's first word. Section 3 is what the speech-to-text service typed from that clip; the microphone hears the enumerator too, so prompts like "shabash" can appear between the child's words. Section 4 has one row per scorer with a colour chip for every printed word: the enumerator row is the live tablet marking, the official score; the baseline row is the first automatic method, which matches transcript words to printed words by spelling; each model row is that model's own judgement from the audio or from the transcript. Red where the enumerator has green means the scorer flagged too much; green where the enumerator has red means it waved a mistake through; grey means skipped or never reached; faded means no verdict. "Attempted" is the furthest word reached. Section 5's "difference from enumerator" is each scorer's correct count minus the enumerator's: near zero is good, a large positive number is too lenient, a large negative number too harsh. Section 6 is the second human's re-listen.</div>'''

CSS = """body{font:15px/1.55 Inter,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;padding:0 20px 60px;color:#1D2025;background:#F9FAFB}.wrap{max-width:1100px;margin:0 auto}
h1{color:#001F3F;font-size:26px}h2{color:#001F3F;font-size:19px;margin-top:34px;border-top:3px solid #F06E42;display:inline-block;padding-top:10px}
.meta{color:#6B7590;font-size:13px}table{border-collapse:collapse;font-size:13.5px;margin:12px 0}th,td{padding:6px 10px;border-bottom:1px solid #E9EDF4;text-align:left}th{font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;color:#6B7590}
.vrow{display:grid;grid-template-columns:200px 1fr;gap:10px;padding:8px 0;border-bottom:1px solid #E9EDF4;align-items:start}.lab{font-weight:600;color:#001F3F;font-size:13px}.chips{display:flex;flex-wrap:wrap;gap:4px;direction:rtl}.chips.ltr{direction:ltr}
.w{border:1px solid #D9DEE8;border-radius:4px;padding:1px 6px;font-size:13px;background:#fff}.w.ok{background:#E6F7EC;border-color:#21C45D}.w.bad{background:#FDEDE6;border-color:#F06E42;color:#B23A12;text-decoration:line-through}.w.skip{background:#F3F4F6;color:#9AA3B5}.w.na{opacity:.4}
.note{grid-column:2;font-size:12.5px;color:#6B7590}.legend span{margin-right:12px}.box{background:#fff;border:1px solid #D9DEE8;padding:12px 14px;margin:10px 0}code{background:#EEF2F9;padding:1px 5px;border-radius:3px}
nav a{margin-right:16px;font-size:13.5px}"""

def page(title, body):
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Noto+Nastaliq+Urdu&display=swap"><style>{CSS}</style></head><body><div class="wrap"><nav><a href="../index.html">EGRA in Five Minutes</a><a href="index.html">All worked examples</a><a href="../harness/results.html">Evaluation</a></nav>{body}</div></body></html>'

if __name__ == '__main__':
    refs = {s: json.load(open(f'harness/reference/{s}.json'))['ref'] for s in SUBS}
    # candidate windows: count models with a usable result per (file, sub) from the cached JSONs (the CSV can be stale)
    cov = {}
    for p in glob.glob('harness/windows/*__*__*.json'):
        parts = os.path.basename(p).split('__')
        if len(parts) < 4:
            continue
        f, sub = parts[2], parts[3].replace('.json', '')
        try:
            if json.load(open(p)).get('result'):
                cov.setdefault((f, sub), set()).add(parts[1])
        except Exception:
            pass
    picks = []
    for sub in SUBS:
        cands = [f for (f, ss), ms in cov.items() if ss == sub and len(ms) >= 8]
        random.shuffle(cands)
        def ecount(f):
            gt = json.load(open('harness/gt/' + f)); sc = gt['scores']; pre, lang = SUBS[sub][1], SUBS[sub][2]
            return float(sc.get(f'{pre}_60s_correct_{lang}') or sc.get(f'{pre}_reading_correct_{lang}') or 0)
        chosen = sorted(cands[:N_PER * 3], key=ecount)
        step = max(1, len(chosen) // N_PER)
        picks += [(sub, f[:20]) for f in chosen[::step][:N_PER]]
    print('candidates per subtask', {sub: sum(1 for (f, ss), ms in cov.items() if ss == sub and len(ms) >= 8) for sub in SUBS})
    drive = None; folder_link = None
    try:
        drive = drive_client(); folder_id, folder_link = ensure_folder(drive)
    except Exception as ex:
        print('Drive unavailable, clips will be local only:', str(ex)[:120])
    index_rows = []
    for k, (sub, fshort) in enumerate(picks, 1):
        title, pre, lang = SUBS[sub]; ref = refs[sub]
        segp = next(p for p in glob.glob('harness/segments_llm/google_gemini-2.5-pro__*.json') if os.path.basename(p).split('__')[1].startswith(fshort))
        r = json.load(open(segp)); f = r['file']; s = next(x for x in r['segments'] if x['sub'] == sub)
        gt = json.load(open('harness/gt/' + f)); sc = gt['scores']; flags = gt['items'].get(sub) or []
        trp = 'harness/whisper_en/' + f if lang == 'eng' else 'harness/soniox/' + f
        tr = json.load(open(trp)); wt = rs.words_with_time(rs.child_tokens(tr, s['start_s'], s['end_s'])); t0 = wt[0][1]; hyp = [x for x, t in wt if t - t0 <= 60.5]
        st, ins = rs.align(ref, hyp); att_b = rs.last_attempted(st)
        e_corr = sc.get(f'{pre}_60s_correct_{lang}') or sc.get(f'{pre}_reading_correct_{lang}'); e_att = sc.get(f'{pre}_60s_attempted_{lang}') or sc.get(f'{pre}_reading_attempted_{lang}')
        # clip
        clip = f'harness/examples/_clips/ex{k:02d}_{sub}.mp3'
        if not os.path.exists(clip):
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', f'{max(0, t0 - 0.5):.2f}', '-to', f'{t0 + 61:.2f}', '-i', 'audio/' + f.replace('.json', ''), '-ar', '16000', '-ac', '1', '-b:a', '48k', clip], check=True)
        link = upload(drive, folder_id, clip, os.path.basename(clip)) if drive else None
        # QA reviewer verdict for this subtask
        qa_line = ''
        NICE = {'correct': 'agreed with the enumerator', 'incorrect': 'disagreed with the enumerator', 'unknown': 'could not tell from the audio'}
        for q in gt.get('qa', []):
            try:
                v = json.loads(q['verdicts']).get(sub, {})
                fields = {kk: vv for kk, vv in v.items() if not kk.startswith('__')}
                if not fields or all(str(vv) in ('None', '') for vv in fields.values()):
                    continue
                parts = []
                for kk, vv in fields.items():
                    what = 'the correct count' if 'correct' in kk else ('the attempted count' if 'attempt' in kk else kk)
                    parts.append(f'on {what} the reviewer {NICE.get(str(vv), str(vv))}')
                proto = v.get('__protocol_followed')
                qa_line = 'The second human (' + html.escape(str(q.get('reviewer'))) + ') re-listened: ' + '; '.join(parts) + ('; the enumerator followed the protocol' if proto is True else ('; the reviewer flagged a protocol slip' if proto is False else '')) + '.'
                try:
                    cm = json.loads(q.get('comments') or '{}').get(sub)
                    if cm:
                        qa_line += ' Reviewer comment: “' + html.escape(str(cm)) + '”'
                except Exception:
                    pass
            except Exception:
                pass
        # model rows
        e_att_i = int(float(e_att or 0)); e_corr_i = int(float(e_corr or 0))
        enum_verd = [('correct' if fl == 0 else 'wrong') if (i < e_att_i and fl is not None) else 'skipped' for i, fl in enumerate(flags)]
        rows_html = [row_html('Enumerator (tablet, live)', ref, enum_verd, f'{e_corr_i} correct of {e_att_i} attempted in 60 s (words after the 60-second point are grey: the export records 0 for both "correct" and "never reached", so they are only known up to the attempted count)', lang),
                     row_html('Baseline: speech-to-text + spelling alignment', ref, st, f'{sum(1 for x in st[:att_b] if x == "correct")} correct of {att_b} attempted; {ins} extra words the child said are ignored', lang)]
        counts = [('Enumerator', e_corr_i, e_att_i), ('Baseline: speech-to-text + alignment', sum(1 for x in st[:att_b] if x == 'correct'), att_b)]
        n_models = 0; n_noanswer = 0
        for model in ORDER:
            for arm in ('audio', 'text'):
                p = f"harness/windows/{arm}__{model.replace('/', '_')}__{f}__{sub}.json"
                if not os.path.exists(p):
                    continue
                res = json.load(open(p)); j = res.get('result'); n_models += 1
                if not j:
                    n_noanswer += 1
                    rows_html.append(row_html(SHORT.get(model, model), ref, [], 'The model returned no usable answer for this window (its reply was not in the requested format).', lang))
                    counts.append((SHORT.get(model, model), None, None)); continue
                verd = [x.get('v') for x in j.get('words', [])]; att = max((i + 1 for i, v in enumerate(verd) if v != 'skipped'), default=0)
                mc = sum(1 for v in verd[:att] if v == 'correct'); note = str(j.get('notes', '') or '')
                rows_html.append(row_html(SHORT.get(model, model), ref, verd, f'{mc} correct of {att} attempted · model note: {note[:140]}{"…" if len(note) > 140 else ""}', lang))
                counts.append((SHORT.get(model, model), mc, att))
        ct = '<table><thead><tr><th>Scorer</th><th>Words correct</th><th>Words attempted (furthest word reached)</th><th>Difference from enumerator (correct)</th><th>Difference (attempted)</th></tr></thead><tbody>' + ''.join(
            (f'<tr><td>{html.escape(str(n))}</td><td>{c}</td><td>{a}</td><td>{c - e_corr_i:+}</td><td>{a - e_att_i:+}</td></tr>' if c is not None else f'<tr><td>{html.escape(str(n))}</td><td>—</td><td>—</td><td>no usable answer</td><td>—</td></tr>') for n, c, a in counts) + '</tbody></table>'
        body = f'''<h1>Worked example {k}: {html.escape(title)}</h1>
<p class="meta">Recording {html.escape(f[:12])}… · grade {int(float(gt.get("grade") or 0))} · age {int(float(gt.get("age") or 0))} · enumerator #{int(__import__("hashlib").md5(str(gt.get("enumerator")).encode()).hexdigest()[:4], 16) % 97:02d} · window {s["start_s"]:.0f}–{s["end_s"]:.0f} s of the session, 60-s clock from the child's first word at {t0:.1f} s</p>
{HOWTO}
<h2>1. What the child was supposed to read</h2><div class="box chips{" ltr" if lang == "eng" else ""}" style="display:flex;flex-wrap:wrap;gap:6px;font-size:16px">{" ".join(f'<span class="w">{i + 1}. {html.escape(x)}</span>' for i, x in enumerate(ref))}</div>
<p class="meta">The study export holds only right/wrong flags, not the text itself, so this text was reconstructed from 30 children's reads with an LLM; a word or two of it may itself be wrong, which would show up as the same "mistake" in every scorer's row.</p>
<h2>2. The child's audio</h2><div class="box">{"<a href=" + chr(34) + link + chr(34) + ">Play the 60-second clip (Drive, Taleemabad accounts)</a>" if link else "Clip kept in the private project folder: " + html.escape(clip)}<br><span class="meta">8 kHz classroom recording from the May 2026 study, upsampled. Folder: {("<a href=" + chr(34) + folder_link + chr(34) + ">worked-examples clips</a>") if folder_link else "—"}</span></div>
<h2>3. What the speech-to-text service heard</h2><div class="box" style="{"direction:rtl;font-family:'Noto Nastaliq Urdu',serif;font-size:17px;line-height:2" if lang == "urd" else ""}">{html.escape(" ".join(hyp))}</div>
<p class="meta">{"whisper-1 forced to English" if lang == "eng" else "Soniox stt-async-v3, Urdu hint"} · {len(hyp)} words inside the 60-s window. The enumerator's own words (prompts, "shabash") are included when they fall inside the window.</p>
<h2>4. Every scorer's verdict on every word</h2>
<p class="legend"><span class="w ok">read correctly</span> <span class="w bad">wrong</span> <span class="w skip">skipped or not reached</span> <span class="w na">no verdict</span></p>
<div class="box">{"".join(rows_html)}</div>
<h2>5. The counts</h2>{ct}
<h2>6. The second human</h2><div class="box">{qa_line if qa_line else "No re-listen was recorded for this subtask."}</div>'''
        open(f'{OUT}/ex{k:02d}.html', 'w').write(page(f'Worked example {k}', body))
        index_rows.append(f'<tr><td><a href="ex{k:02d}.html">Example {k}</a></td><td>{html.escape(title)}</td><td>grade {int(float(gt.get("grade") or 0))}</td><td>{e_corr_i} / {e_att_i}</td><td>{n_models} models{f" ({n_noanswer} gave no usable answer)" if n_noanswer else ""}</td></tr>')
        print('example', k, sub, f[:12], 'enum', e_corr, 'link', bool(link))
    rv = open('harness/examples/REVIEW.md').read() if os.path.exists('harness/examples/REVIEW.md') else ''
    def section(name):
        import re as _re
        m = _re.search(r'## ' + name + r'\n(.*?)(?=\n## |\Z)', rv, _re.S)
        return '<div class="box">' + ''.join(f'<p>{html.escape(para.strip())}</p>' for para in m.group(1).strip().split('\n\n')) + '</div>' if m else ''
    HOWTO_INDEX = ('<h2>How to read a worked example</h2>' + section('How to read a worked example') + '<h2>What these twelve pages show</h2>' + section('What these twelve pages show')) if rv else ''
    idx = f'''<h1>Worked examples: how each score was produced</h1>
<p>Twelve real windows from the evaluation, chosen to span weak and strong readers. Each page shows the printed text, the child's clip, the speech-to-text transcript, the enumerator's live marks, the round-1 alignment verdicts, and every model's per-word verdicts, then the counts side by side and the second human's review. Nothing is summarised away: what you see is exactly what the scorer saw and what it returned.</p>
<div class="box"><strong>Where the audio lives.</strong> The clips are children's voices, so they are in a Drive folder readable by Taleemabad, hellorumi.ai and NIETE accounts, not on this public site: {("<a href=" + chr(34) + folder_link + chr(34) + ">open the folder</a>") if folder_link else "private project folder"}.</div>
{HOWTO_INDEX}
<table><thead><tr><th>Page</th><th>Subtask</th><th>Grade</th><th>Enumerator: correct / attempted</th><th>Scorers shown</th></tr></thead><tbody>{"".join(index_rows)}</tbody></table>
<p class="meta">Generated by the harness (step 14) from cached model responses; rerunning it produces the same pages.</p>'''
    open(f'{OUT}/index.html', 'w').write(page('Worked examples', idx))
    print('done', len(picks), 'examples; folder', folder_link)
