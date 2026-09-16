"""Build the self-contained GitHub Pages site for the EGRA-in-five-minutes plan into ./site.
Includes: the plan (index.html), every research doc, the harness results + scripts + aggregate CSVs, the baseline,
probe findings, the TIP notes, the alignment-call summary, a files index, and a sources index of every external link.
Excludes anything with child data: recordings, the SurveyCTO export, transcripts, per-child JSON, reference stimuli.
Run: uv run --with markdown python build_site.py
"""
import os, re, shutil, csv, html, glob, collections
import markdown

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, 'site')
REPO = 'https://github.com/hyasin270/egra-five-minutes'

DOCS = [  # (source path, output path, title, one-line description)
    ('INVESTIGATION.md', 'investigation.html', 'Investigation index', 'What was asked, what is in the folder, headline findings, open decisions'),
    ('BASELINE.md', 'baseline.html', 'Baseline: the May 2026 study', 'The corpus, the 21-minute enumerator timing baseline, the QA review layer'),
    ('harness/HARNESS_RESULTS.md', 'harness/results.html', 'The evaluation', 'Every model we tested, one table per subtask, the human floor and the baseline beside every number, and the stack we recommend'),
    ('research/01_EGRA_EGMA_structure.md', 'research/01-egra-egma-structure.html', 'EGRA and EGMA structure', 'Subtasks, timing, stop rules, Urdu adaptations, benchmarks, automated-scoring literature'),
    ('research/02_model_landscape.md', 'research/02-model-landscape.html', 'Model landscape', 'Every pronunciation, ASR, phone-recognition, audio-LLM and vision option checked, with locale lists and prices'),
    ('research/03_current_reading_pipeline.md', 'research/03-current-reading-pipeline.html', 'What the main bot already has', 'The reading pipeline and the live ASER tool, file by file'),
    ('research/04_niete_observe_hitl.md', 'research/04-niete-observe-hitl.html', 'The NIETE observe HITL flow', 'How the AI pre-fill and coach correction work today; hook points; reuse map'),
    ('research/05_what_a_recording_can_yield.md', 'research/05-what-a-recording-can-yield.html', 'What a recording can yield', 'Constructs recoverable from a read-aloud beyond WCPM, with evidence and phase'),
    ('research/06_assessment_batteries_walkthrough.md', 'research/06-assessment-batteries.html', 'Assessment batteries walkthrough', 'EGRA, EGMA, ICAN, TIP, ASER, ELANA, DIBELS, MELQO, Literacy Boost, Pakistan incumbents, AI readers'),
    ('research/07_model_deep_dive.md', 'research/07-model-deep-dive.html', 'Model deep dive', 'Child-speech ASR, Urdu models, phone/GOP stacks, prosody, audio LLMs, maths ITN, vision; the eval shortlist'),
    ('probes/PROBE1_FINDINGS.md', 'probes/probe1.html', 'Probe 1: an audio LLM on a whole session', 'Gemini 2.5 Pro and Flash segment and score one 17-minute enumerator recording'),
    ('probes/PROBE2_FINDINGS.md', 'probes/probe2.html', 'Probe 2: production STT on the Urdu block', 'Soniox timestamps, diarisation and the "STT cuts, LLM labels" rule'),
    ('tips/TIP_NOTES.md', 'tips/tip-notes.html', 'The TIP diagnostic (LEAPS/CERP)', 'What the written placement test contains and how it relates to ours'),
    ('meetings/2026-09-15_alignment-call.md', 'meetings/alignment-call-2026-09-15.html', 'Alignment call, 15 Sep 2026', 'Decisions with timestamps; how the transcript was recovered'),
]
SCRIPTS = sorted(glob.glob(os.path.join(ROOT, 'harness', '*.py')) + glob.glob(os.path.join(ROOT, 'harness', '*.sh')) +
                 [os.path.join(ROOT, f) for f in ('download_drive_audio.py', 'baseline_timings.py', 'audio_durations.py', 'download_tips_folder.py', 'build_site.py')] +
                 glob.glob(os.path.join(ROOT, 'probes', '*.py')))
CSVS = [  # aggregate tables only; no names, no phones, no child transcripts
    ('baseline_subtask_timings.csv', 'Per-subtask enumerator timings (seconds)'),
    ('harness/human_floor.csv', 'Human floor: reviewer agreement with the enumerator per subtask'),
    ('harness/reading_summary.csv', 'Reading counts: machine vs enumerator per subtask, with window-failure split'),
    ('harness/round2_windows.csv', 'Sixty-second windows: every audio and text model vs the enumerator, with baseline and human floor'),
    ('harness/round2_comprehension.csv', 'Comprehension graders vs the enumerator'),
    ('harness/round2_segmenter.csv', 'Segmenter labellers vs the tablet timestamps'),
    ('harness/round2_maths.csv', 'Maths graders vs the enumerator, by subtask'),
    ('harness/window_scores.csv', 'Per-window rows behind the sixty-second-window table (file ids only)'),
    ('harness/comprehension_scores.csv', 'Per-child rows behind the comprehension table'),
    ('harness/reading_scores.csv', 'Reading counts per recording window (file ids only)'),
    ('harness/reading_items.csv', 'Per-word machine vs enumerator flags (subtask, machine_wrong, enum_wrong)'),
    ('harness/segmenter_llm_google_gemini-2.5-pro.csv', 'Segmenter agreement with tablet timestamps per recording'),
    ('harness/maths_scores_google_gemini-2.5-pro.csv', 'Maths from speech: machine vs enumerator counts per recording'),
    ('harness/english_results.csv', 'English windows: SpeechAce and STT-diff vs enumerator per recording'),
    ('harness/segmenter_results.csv', 'Rule-based segmenter (v1) results'),
]

CSS = """
:root{--navy:#001F3F;--coral:#F06E42;--gold:#F5B301;--bg:#F9FAFB;--surface:#fff;--ink:#1D2025;--ink2:#4B5568;--muted:#6B7590;--line:#D9DEE8;--soft:#E9EDF4;--tint:#EEF2F9}
@media (prefers-color-scheme:dark){:root{--navy:#8FB0FF;--bg:#0B1226;--surface:#111A36;--ink:#E6EAF4;--ink2:#B9C2D6;--muted:#8A95B0;--line:#2A365C;--soft:#1C2747;--tint:#16214A}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;padding:0 20px 80px}
.wrap{max-width:960px;margin:0 auto}a{color:var(--navy)}
nav.top{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:13.5px;padding:18px 0;border-bottom:1px solid var(--line);margin-bottom:24px}
nav.top a{text-decoration:none;color:var(--ink2)}nav.top a.brand{font-weight:700;color:var(--navy)}
h1{font-size:clamp(26px,4vw,38px);line-height:1.1;color:var(--navy);margin:16px 0 6px}h2{font-size:22px;margin-top:44px;padding-top:14px;border-top:3px solid var(--coral);display:inline-block;color:var(--navy)}
h3{font-size:17px;margin-top:26px;color:var(--navy)}h4{margin-top:20px}
.lede{color:var(--ink2);font-size:17px;max-width:64ch}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin:14px 0;display:block;overflow-x:auto}th,td{text-align:left;vertical-align:top;padding:7px 9px;border-bottom:1px solid var(--soft)}
th{font-size:11.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--line)}
code{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.88em;background:var(--tint);padding:1px 5px;border-radius:3px}
pre{background:var(--surface);border:1px solid var(--line);padding:14px;overflow-x:auto;font-size:12.5px;line-height:1.45}pre code{background:none;padding:0}
blockquote{border-left:3px solid var(--coral);margin:16px 0;padding:6px 16px;color:var(--ink2)}
ul,ol{padding-left:22px}li{margin:5px 0}
.meta{font-size:13px;color:var(--muted)}.card{background:var(--surface);border:1px solid var(--line);padding:12px 14px;margin:10px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}
footer{margin-top:60px;padding-top:16px;border-top:1px solid var(--line);font-size:13px;color:var(--muted)}
"""

def nav(depth):
    up = '../' * depth
    return (f'<nav class="top"><a class="brand" href="{up}index.html">EGRA in Five Minutes</a><a href="{up}index.html#experiment">Experiment</a>'
            f'<a href="{up}harness/results.html">Harness results</a><a href="{up}files.html">All files</a><a href="{up}sources.html">Sources</a>'
            f'<a href="{REPO}">Repository</a></nav>')

def page(title, body, depth, lede=''):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)} · EGRA in Five Minutes</title><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">'
            f'<style>{CSS}</style></head><body><div class="wrap">{nav(depth)}<h1>{html.escape(title)}</h1>'
            f'{("<p class=lede>" + html.escape(lede) + "</p>") if lede else ""}{body}'
            f'<footer>Part of the EGRA-in-five-minutes plan · Taleemabad / Rumi · built {__import__("datetime").date.today().isoformat()} · <a href="{REPO}">repository</a></footer></div></body></html>')

def md_to_html(text, src_path):
    # rewrite relative .md links to their .html twins
    mapping = {s: o for s, o, _, _ in DOCS}
    def repl(m):
        target = m.group(2)
        base = os.path.dirname(src_path)
        norm = os.path.normpath(os.path.join(base, target)) if not target.startswith(('http', '#')) else target
        if norm in mapping:
            depth = src_path.count('/')
            return f'[{m.group(1)}]({"../" * depth}{mapping[norm]})'
        return m.group(0)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+\.md)\)', repl, text)
    return markdown.markdown(text, extensions=['tables', 'fenced_code', 'toc', 'sane_lists'])

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w', encoding='utf-8').write(content)

def build():
    os.makedirs(OUT, exist_ok=True)
    for name in os.listdir(OUT):  # clear everything except the site's own .git
        if name == '.git':
            continue
        pth = os.path.join(OUT, name)
        shutil.rmtree(pth) if os.path.isdir(pth) else os.remove(pth)
    urls_by_doc = collections.OrderedDict()
    # 1. docs
    for src, out, title, desc in DOCS:
        text = open(os.path.join(ROOT, src), encoding='utf-8').read()
        urls_by_doc[title] = sorted(set(re.findall(r'https?://[^\s)\]>"\'`]+', text)))
        body = md_to_html(text, src)
        write(os.path.join(OUT, out), page(title, body, out.count('/'), desc))
    # 2. scripts: raw copy + syntax page
    for sp in SCRIPTS:
        rel = os.path.relpath(sp, ROOT)
        raw_out = os.path.join(OUT, 'src', rel)
        os.makedirs(os.path.dirname(raw_out), exist_ok=True); shutil.copy(sp, raw_out)
        code = open(sp, encoding='utf-8').read()
        doc = re.search(r'"""(.*?)"""', code, re.S)
        body = f'<p class="meta">Raw file: <a href="{"../" * (rel.count("/") + 1)}src/{rel}">{rel}</a></p><pre><code>{html.escape(code)}</code></pre>'
        write(os.path.join(OUT, 'code', rel + '.html'), page(rel, body, rel.count('/') + 1, (doc.group(1).strip().split("\n")[0] if doc else '')))
    # 3. csvs: raw copy + table page (first 300 rows)
    for rel, desc in CSVS:
        sp = os.path.join(ROOT, rel)
        if not os.path.exists(sp):
            continue
        raw_out = os.path.join(OUT, 'data', rel); os.makedirs(os.path.dirname(raw_out), exist_ok=True); shutil.copy(sp, raw_out)
        rows = list(csv.reader(open(sp, encoding='utf-8')))
        head, body_rows = rows[0], rows[1:]
        t = '<table><thead><tr>' + ''.join(f'<th>{html.escape(h)}</th>' for h in head) + '</tr></thead><tbody>'
        t += ''.join('<tr>' + ''.join(f'<td>{html.escape(c)}</td>' for c in r) + '</tr>' for r in body_rows[:300]) + '</tbody></table>'
        note = f'<p class="meta">{len(body_rows)} rows{" (first 300 shown)" if len(body_rows) > 300 else ""} · raw file: <a href="{"../" * (rel.count("/") + 1)}data/{rel}">{rel}</a></p>'
        write(os.path.join(OUT, 'tables', rel + '.html'), page(rel, note + t, rel.count('/') + 1, desc))
    # 4. index.html from PLAN.html with the files section rebuilt
    plan = open(os.path.join(ROOT, 'PLAN.html'), encoding='utf-8').read()
    files_section = build_files_section()
    plan = re.sub(r'<section id="files">.*?</section>', files_section, plan, count=1, flags=re.S)
    plan = plan.replace('<nav class="toc">', f'<nav class="toc"><a href="files.html">All files</a><a href="sources.html">Sources</a><a href="{REPO}">Repository</a>')
    plan = plan.replace('<code>harness/HARNESS_RESULTS.md</code>', '<a href="harness/results.html">harness/HARNESS_RESULTS.md</a>')
    plan = plan.replace('(they are in the <code>harness/</code> folder)', '(they are all <a href="files.html#harness">linked on the files page</a>)')
    head = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<style>body{margin:0;font-size:14px}img{max-width:100%}[hidden]{display:none!important}</style></head><body>')
    write(os.path.join(OUT, 'index.html'), head + plan + '</body></html>')
    # 5. files.html and sources.html
    write(os.path.join(OUT, 'files.html'), page('All files', files_section.replace('<section id="files">', '').replace('</section>', '').replace('<h2>Where everything is</h2>', ''), 0, 'Every document, script and table behind the plan, plus private team links to the recordings and the study export.'))
    write(os.path.join(OUT, 'sources.html'), page('Sources', build_sources(urls_by_doc), 0, 'Every external link cited in the research documents, grouped by document. The tests themselves are at the top.'))
    # 6. worked examples (generated by harness/14) and charts (harness/13)
    ex = os.path.join(ROOT, 'harness', 'examples')
    if os.path.isdir(ex):
        os.makedirs(os.path.join(OUT, 'examples'), exist_ok=True)
        for fn in os.listdir(ex):
            if fn.endswith('.html'):
                shutil.copy(os.path.join(ex, fn), os.path.join(OUT, 'examples', fn))
    ch = os.path.join(ROOT, 'harness', 'charts')
    if os.path.isdir(ch):
        os.makedirs(os.path.join(OUT, 'charts'), exist_ok=True)
        for fn in os.listdir(ch):
            if fn.endswith('.png'):
                shutil.copy(os.path.join(ch, fn), os.path.join(OUT, 'charts', fn))
    write(os.path.join(OUT, '.nojekyll'), '')
    print('built', OUT)

def build_files_section():
    parts = ['<section id="files">', '<h2>Where everything is</h2>']
    parts.append('<h3>Documents</h3><div class="grid">')
    for src, out, title, desc in DOCS:
        parts.append(f'<div class="card"><a href="{out}"><strong>{html.escape(title)}</strong></a><br><span class="meta">{html.escape(desc)} · <code>{src}</code></span></div>')
    parts.append('</div><h3 id="harness">Harness scripts (run in order to reproduce every number)</h3><ol>')
    for sp in SCRIPTS:
        rel = os.path.relpath(sp, ROOT)
        code = open(sp, encoding='utf-8').read(); doc = re.search(r'"""(.*?)"""', code, re.S)
        first = html.escape(doc.group(1).strip().split('\n')[0]) if doc else ''
        parts.append(f'<li><a href="code/{rel}.html"><code>{rel}</code></a> — {first} <span class="meta">(<a href="src/{rel}">raw</a>)</span></li>')
    parts.append('</ol><h3>Result tables</h3><ul>')
    for rel, desc in CSVS:
        if os.path.exists(os.path.join(ROOT, rel)):
            parts.append(f'<li><a href="tables/{rel}.html"><code>{rel}</code></a> — {html.escape(desc)} <span class="meta">(<a href="data/{rel}">csv</a>)</span></li>')
    parts.append('</ul><h3>Worked examples</h3><p><a href="examples/index.html">Twelve real windows</a>, each showing the printed text, the clip (Drive, team accounts), the transcript, the enumerator\'s marks and every model\'s per-word verdicts side by side.</p><h3>Private team data (Google Drive, Taleemabad accounts only)</h3><ul>'
                 '<li><a href="https://drive.google.com/drive/folders/19tfSEeBaOchNwSB2VNZd9s9PmEpDAIkG">The May 2026 study folder</a> — the 207 enumerator recordings (<code>AA_&lt;uuid&gt;_enumerator.m4a</code>), the SurveyCTO export <code>EGRA_EGMA client N=2233.xlsx</code> (one row per child, 1,364 columns), and the reviewer workbook <code>Data.xlsx</code> (1,462 QA re-listens). These hold child data and are not copied into this repository.</li>'
                 '<li><a href="https://drive.google.com/drive/folders/1HA_Xhe5leHRIwbj-OkWmv9SgEdwa0U5D">The TIP assessments folder</a> — the LEAPS/CERP written diagnostic PDFs (English/Urdu all classes; maths Class 1–5). The read-through is in the TIP notes above.</li>'
                 '<li>The working folder with every intermediate (transcripts, per-child JSON, reconstructed stimuli, the full alignment-call transcript): <code>06_Logs &amp; Misc/Reports/Active/EGRA Student Assessment - Sep 2026/</code> in the Rumi workspace.</li></ul>')
    parts.append('</section>')
    return '\n'.join(parts)

TESTS = [
    ('EGRA Toolkit, 2nd edition (RTI / USAID)', 'https://pdf.usaid.gov/pdf_docs/PA00M4TN.pdf'),
    ('EGMA Toolkit (RTI / USAID, 2014)', 'https://pdf.usaid.gov/pdf_docs/PA00KNG5.pdf'),
    ('ASER Pakistan (ITA)', 'https://aserpakistan.org/'),
    ('ICAN, International Common Assessment of Numeracy (PAL Network)', 'https://palnetwork.org/ican/'),
    ('PAL-ELANA literacy and numeracy assessment', 'https://palnetwork.org/elana/'),
    ('DIBELS 8th edition (University of Oregon)', 'https://dibels.uoregon.edu/'),
    ('Acadience Reading', 'https://acadiencelearning.org/'),
    ('MELQO / MODEL (UNESCO, World Bank)', 'https://unesdoc.unesco.org/ark:/48223/pf0000248053'),
    ('Targeted Instruction Program (LEAPS / CERP)', 'https://www.leapsprogram.org/'),
    ('Tangerine (RTI tablet EGRA)', 'https://www.tangerinecentral.org/'),
    ('Google Read Along', 'https://readalong.google/'),
    ('Amira Learning', 'https://www.amiralearning.com/'),
    ('Microsoft Azure Pronunciation Assessment', 'https://learn.microsoft.com/azure/ai-services/speech-service/how-to-pronunciation-assessment'),
    ('SpeechAce API', 'https://www.speechace.com/api-plans/'),
    ('Soniox speech-to-text', 'https://soniox.com/'),
    ('OpenAI Whisper transcription', 'https://platform.openai.com/docs/guides/speech-to-text'),
    ('Meta Omnilingual ASR', 'https://github.com/facebookresearch/omnilingual-asr'),
    ('ZIPA phone recogniser (ACL 2025)', 'https://github.com/lingjzhu/zipa'),
    ('Montreal Forced Aligner', 'https://montreal-forced-aligner.readthedocs.io/'),
]

def build_sources(urls_by_doc):
    parts = ['<h2>The tests and tools</h2><ul>']
    for name, url in TESTS:
        parts.append(f'<li><a href="{url}">{html.escape(name)}</a> <span class="meta">{html.escape(url)}</span></li>')
    parts.append('</ul>')
    for doc, urls in urls_by_doc.items():
        if not urls:
            continue
        parts.append(f'<h2>{html.escape(doc)}</h2><ul>')
        for u in urls:
            u = u.rstrip('.,;:')
            parts.append(f'<li><a href="{html.escape(u)}">{html.escape(u)}</a></li>')
        parts.append('</ul>')
    return '\n'.join(parts)

if __name__ == '__main__':
    build()
