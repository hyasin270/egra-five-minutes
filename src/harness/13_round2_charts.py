"""Harness round 2, step 13: house-style charts of the round-2 results for the board post and the site.
Run: uv run --with matplotlib --with numpy --with pandas python harness/13_round2_charts.py
"""
import os, sys, pandas as pd
sys.path.insert(0, os.path.expanduser('~/.claude/skills/notion-board/reference'))
import economist_chart as ec

os.makedirs('harness/charts', exist_ok=True)
SRC = 'Rumi EGRA harness, 187 enumerator recordings (Rawalpindi, May 2026), 8 kHz classroom audio'
SHORT = {'google/gemini-3.1-pro-preview': 'Gemini 3.1 Pro (audio)', 'google/gemini-3.8-flash': 'Gemini 3.8 Flash (audio)', 'google/gemini-3.5-flash-lite': 'Gemini 3.5 Flash-Lite (audio)',
         'google/gemini-2.5-flash': 'Gemini 2.5 Flash (audio)', 'openai/gpt-audio': 'GPT audio (audio)', 'openai/gpt-audio-mini': 'GPT audio mini (audio)', 'xiaomi/mimo-v2.5': 'MiMo 2.5 (audio)',
         'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free': 'Nemotron omni (audio)', 'mistralai/voxtral-small-24b-2507': 'Voxtral small (audio)',
         'anthropic/claude-sonnet-5': 'Claude Sonnet 5 (transcript)', 'openai/gpt-5-mini': 'GPT-5 mini (transcript)', 'google/gemini-3-flash-preview': 'Gemini 3 Flash (transcript)', 'deepseek/deepseek-v3.2': 'DeepSeek 3.2 (transcript)', 'google/gemini-2.5-flash-lite': 'Gemini 2.5 Flash-Lite (transcript)'}
w = pd.read_csv('harness/round2_windows.csv')
w['label'] = w.model.map(SHORT).fillna(w.model)

# Chart 1: count error (MAE) per scorer, averaged over the three subtasks, baseline included
rows = [(label, g.MAE.mean()) for label, g in w.groupby('label')]
rows.append(('Baseline: speech-to-text + alignment', float(w.baseline_MAE.mean())))
rows.sort(key=lambda r: r[1])
fig = ec.bar_h(title='How far off is each scorer on "words read correctly in 60 seconds"?', labels=[r[0] for r in rows], values=[r[1] for r in rows],
               subtitle='Mean absolute error in words vs the enumerator, averaged over Urdu story, Urdu word list and English story. Lower is better. Each scorer saw the printed text plus the clip (audio) or its transcript.',
               source=SRC, xaxis_label='words off, on average', value_fmt='{:.1f}')
ec.save_chart(fig, 'harness/charts/round2_count_mae.png')

# Chart 2: per-word F1 (balance of precision and recall of wrong-word flags), Urdu story
u = w[w.subtask == 'orf_urd'].copy()
u['f1'] = 2 * u.word_precision * u.word_recall / (u.word_precision + u.word_recall).replace(0, float('nan'))
u = u.dropna(subset=['f1']).sort_values('f1', ascending=False)
it = pd.read_csv('harness/reading_items.csv'); it = it[it['sub'] == 'orf_urd']
tp = ((it.machine_wrong == 1) & (it.enum_wrong == 1)).sum(); fp = ((it.machine_wrong == 1) & (it.enum_wrong == 0)).sum(); fn = ((it.machine_wrong == 0) & (it.enum_wrong == 1)).sum()
bp, br = tp / max(1, tp + fp), tp / max(1, tp + fn); base_f1 = 100 * 2 * bp * br / max(1e-9, bp + br)
labels = list(u.label) + ['Baseline: speech-to-text + alignment']; values = list(u.f1 * 100) + [base_f1]
order = sorted(range(len(values)), key=lambda i: -values[i])
fig = ec.bar_h(title='Per-word marks on the Urdu story: how well each scorer\'s wrong-word flags match the enumerator', labels=[labels[i] for i in order], values=[values[i] for i in order],
               subtitle=f'F1 of wrong-word flags (balance of precision and recall) vs the enumerator, on words both reached. Higher is better. Human floor for this subtask: {int(u.human_floor_agree.iloc[0])}%. Models that flagged nothing are omitted.',
               source=SRC, xaxis_label='F1, %', value_fmt='{:.0f}')
ec.save_chart(fig, 'harness/charts/round2_word_precision.png')

# Chart 3: comprehension graders
if os.path.exists('harness/round2_comprehension.csv'):
    c = pd.read_csv('harness/round2_comprehension.csv').sort_values('within1', ascending=False)
    c['label'] = c.model.map(lambda m: SHORT.get(m, m).replace(' (transcript)', ''))
    fig = ec.bar_h(title='Grading the child\'s spoken comprehension answers (Urdu, 6 questions)', labels=list(c.label), values=list(c.within1),
                   subtitle='Share of children where the model\'s count of correct answers was within one of the enumerator\'s. Human floor for this subtask: 73%.',
                   source=SRC, xaxis_label='% of children within ±1 answer', value_fmt='{:.0f}%')
    ec.save_chart(fig, 'harness/charts/round2_comprehension.png')
print('charts written')
