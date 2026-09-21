"""Harness round 2, step 12: one table per experiment with the human floor and the Levenshtein baseline beside every
model, plus total spend. Writes harness/ROUND2_RESULTS.md and harness/round2_*.csv.
Run: uv run --with pandas python harness/12_round2_summary.py
"""
import os, json, glob
import pandas as pd

FLOOR = {r['subtask']: r for r in pd.read_csv('harness/human_floor.csv').to_dict('records')}
out = ['# Round 2 — the models we had not tested, on the same 187 recordings', '',
       '**Run:** 2026-09-16 · every number below sits beside the human floor (how often a second human agreed with the enumerator on that subtask) and the round-1 baseline (speech-to-text + Levenshtein alignment on the very same windows). Scripts `10_window_scorers.py`, `11_comprehension_grade.py`, `03b_segmenter_llm.py`, `07_maths_grade.py`; raw responses cached under `harness/windows/`, `harness/comprehension/`, `harness/segments_llm/`, `harness/maths/`.', '']

# ---- 1. window scorers
w = pd.read_csv('harness/window_scores.csv')
w = w.dropna(subset=['machine_correct', 'enum_correct']).copy(); w['enum_correct'] = pd.to_numeric(w.enum_correct)
rows = []
for (arm, model, sub), g in w.groupby(['arm', 'model', 'sub']):
    diff = g.machine_correct - g.enum_correct; bdiff = g.baseline_correct - g.enum_correct
    prec = g.tp.sum() / max(1, g.tp.sum() + g.fp.sum()); rec = g.tp.sum() / max(1, g.tp.sum() + g.fn.sum())
    rows.append(dict(arm=arm, model=model, subtask=sub, n=len(g), count_r=round(g.machine_correct.corr(g.enum_correct), 2), MAE=round(diff.abs().mean(), 1), bias=round(diff.mean(), 1),
                     within5=round(100 * (diff.abs() <= 5).mean()), word_precision=round(prec, 2), word_recall=round(rec, 2),
                     baseline_r=round(g.baseline_correct.corr(g.enum_correct), 2), baseline_MAE=round(bdiff.abs().mean(), 1),
                     human_floor_agree=FLOOR.get(sub, {}).get('agree_pct'), cost_per_window=round(g.cost.mean(), 4) if g.cost.notna().any() else None))
t = pd.DataFrame(rows).sort_values(['subtask', 'arm', 'MAE']); t.to_csv('harness/round2_windows.csv', index=False)
out += ['## 1. Sixty-second reading windows: audio models vs text models vs the baseline', '',
        'Each model sees the exact printed text and either the 60-s clip (audio arm) or the STT transcript of it (text arm), and returns a verdict per word. "count" = words correct in 60 s vs the enumerator; "word precision/recall" = per-word wrong-flags vs the enumerator\'s item flags; the baseline is the round-1 method on the same windows; the human floor is the reviewer–enumerator agreement for that subtask.', '',
        '| Subtask | Arm | Model | n | count r | MAE | bias | within ±5 | word precision | word recall | baseline r / MAE | human floor | $/window |', '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|']
for r in t.to_dict('records'):
    out.append(f"| {r['subtask']} | {r['arm']} | {r['model']} | {r['n']} | {r['count_r']} | {r['MAE']} | {r['bias']:+} | {r['within5']}% | {r['word_precision']} | {r['word_recall']} | {r['baseline_r']} / {r['baseline_MAE']} | {r['human_floor_agree']}% | {r['cost_per_window']} |")
out.append('')

# ---- 2. comprehension
if os.path.exists('harness/comprehension_scores.csv'):
    c = pd.read_csv('harness/comprehension_scores.csv'); rows = []
    for model, g in c.groupby('model'):
        diff = g.machine - g.enum
        rows.append(dict(model=model, n=len(g), r=round(g.machine.corr(g.enum), 2), MAE=round(diff.abs().mean(), 2), bias=round(diff.mean(), 2), exact=round(100 * (diff == 0).mean()), within1=round(100 * (diff.abs() <= 1).mean()), questions_found=round(g.n_q.mean(), 1), cost=round(g.cost.mean(), 4) if g.cost.notna().any() else None))
    t2 = pd.DataFrame(rows).sort_values('MAE'); t2.to_csv('harness/round2_comprehension.csv', index=False)
    out += ['## 2. Urdu reading-comprehension answers graded by text models', '',
            f"Model sees the reconstructed passage and the diarised transcript of the question window; returns a verdict per question. Compared with the enumerator's count out of 6. Human floor for this subtask: reviewer agreed with the enumerator {FLOOR.get('rdcomp_urd', {}).get('agree_pct')}% of the time.", '',
            '| Model | n | r | MAE (questions) | bias | exact | within 1 | questions found (of 6) | $/child |', '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in t2.to_dict('records'):
        out.append(f"| {r['model']} | {r['n']} | {r['r']} | {r['MAE']} | {r['bias']:+} | {r['exact']}% | {r['within1']}% | {r['questions_found']} | {r['cost']} |")
    out.append('')

# ---- 3. segmenter
rows = []
for p in glob.glob('harness/segmenter_llm_*.csv'):
    d = pd.read_csv(p); model = os.path.basename(p)[len('segmenter_llm_'):-4].replace('_', '/', 1)
    d = d.dropna(subset=['within5'])
    if not len(d): continue
    rows.append(dict(model=model, files=len(d), common=int(d.n_common.sum()), within5=round(100 * d.within5.sum() / d.n_common.sum()), within15=round(100 * d.within15.sum() / d.n_common.sum()), mean_abs_start_err=round(d.mean_abs_start_err.mean(), 1), cost_per_file=round(d.cost.mean(), 4) if d.cost.notna().any() else None))
t3 = pd.DataFrame(rows).sort_values('within15', ascending=False); t3.to_csv('harness/round2_segmenter.csv', index=False)
out += ['## 3. Segmenter labeller: which text model finds the subtask windows on the STT timestamps', '',
        'The model reads the diarised, timestamped transcript and names first/last turn per subtask; windows inherit Soniox\'s clock. Compared with the enumerator\'s tablet taps (which precede the child\'s first word by 5–15 s, so "within 15 s" is the fair band).', '',
        '| Model | files | subtasks matched | start within 5 s | within 15 s | mean abs error | $/file |', '|---|---:|---:|---:|---:|---:|---:|']
for r in t3.to_dict('records'):
    out.append(f"| {r['model']} | {r['files']} | {r['common']} | {r['within5']}% | {r['within15']}% | {r['mean_abs_start_err']} s | {r['cost_per_file']} |")
out.append('')

# ---- 4. maths
rows = []
ENUM = {'idnummag': 'idnummag', 'numrep': 'numrep', 'bleffcomp': 'bleffcomp', 'wrdpblm': 'wrdpblm', 'patterns': 'patterns'}
for p in glob.glob('harness/maths_scores_*.csv'):
    d = pd.read_csv(p); model = os.path.basename(p)[len('maths_scores_'):-4].replace('_', '/', 1)
    for sub in ENUM:
        g = d.dropna(subset=[f'{sub}_machine', f'{sub}_enum']).copy()
        if len(g) < 5: continue
        g[f'{sub}_enum'] = pd.to_numeric(g[f'{sub}_enum']); diff = g[f'{sub}_machine'] - g[f'{sub}_enum']
        rows.append(dict(subtask=sub, model=model, n=len(g), r=round(g[f'{sub}_machine'].corr(g[f'{sub}_enum']), 2), MAE=round(diff.abs().mean(), 2), bias=round(diff.mean(), 2), exact=round(100 * (diff == 0).mean()), within1=round(100 * (diff.abs() <= 1).mean()),
                         human_floor_agree=FLOOR.get({'wrdpblm': 'word_problems', 'bleffcomp': 'computation'}.get(sub, sub), {}).get('agree_pct'), cost_per_child=round(d.cost.mean(), 3) if d.cost.notna().any() else None))
t4 = pd.DataFrame(rows).sort_values(['subtask', 'MAE']); t4.to_csv('harness/round2_maths.csv', index=False)
out += ['## 4. Maths from the spoken transcript, by grader model', '',
        'Grader sees the diarised maths-block transcript, no stimulus (the study export has no item bank). Items whose question is spoken (word problems, computation) are gradable; items whose stimulus is on paper (number ID, patterns) are not from audio alone.', '',
        '| Subtask | Model | n | r | MAE (items) | bias | exact | within 1 | human floor | $/child |', '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
for r in t4.to_dict('records'):
    out.append(f"| {r['subtask']} | {r['model']} | {r['n']} | {r['r']} | {r['MAE']} | {r['bias']:+} | {r['exact']}% | {r['within1']}% | {r['human_floor_agree']}% | {r['cost_per_child']} |")
out.append('')

# ---- spend
tot = 0
for pat, skip in [('harness/windows/*.json', ()), ('harness/comprehension/*.json', ()), ('harness/segments_llm/*.json', ('google_gemini-2.5-pro__', 'google_gemini-2.5-flash__')), ('harness/maths/*.json', ('google_gemini-2.5-pro__',))]:
    tot += sum((json.load(open(p)).get('cost') or 0) for p in glob.glob(pat) if not any(s in p for s in skip))
out += ['## Spend', '', f'Round 2 total through OpenRouter: **${tot:.2f}** (budget $50). Round 1 was ≈ $49 across Soniox, whisper-1, Gemini 2.5 Pro and SpeechAce.', '']
open('harness/ROUND2_RESULTS.md', 'w').write('\n'.join(out))
print('\n'.join(out))
