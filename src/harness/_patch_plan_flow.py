"""One-off: replace the invented checking-screen mockup with the accurate WhatsApp Flow design."""
import re
p = 'PLAN.html'; s = open(p, encoding='utf-8').read()

start = s.index('<section id="form">'); end = s.index('<section id="data">')
new = '''<section id="form">
  <h2>The checking screen</h2>
  <div class="prose">
    <p>This is the same mechanism the lesson-observation form uses in Islamabad today. There, after a coach sends a lesson recording, Rumi listens, fills in the observation form and sends a message with a button that says <em>فارم کھولیں</em> ("open the form"). Tapping it opens a WhatsApp Flow: a set of screens that WhatsApp itself draws, where every score is already filled in, the coach changes what they disagree with, taps Next through the screens, and submits. We reuse that exactly, with one form per child instead of per lesson.</p>
    <p>A WhatsApp Flow is not a web page, so the design has to fit what Meta allows. What it can do: fields pre-filled from our server; number boxes; a row of tappable chips (at most 20); radio buttons; dropdowns; a photo picker that opens the camera; one button per screen; up to 50 elements per screen. What it cannot do: <strong>play audio</strong>. There is no sound inside a Flow at all. So the coach does not re-listen inside the form; the recording is their own voice note, already in the chat, and they play it there. Each screen's button sends its values to Rumi as soon as it is tapped, so closing the form to listen and opening it again loses nothing.</p>
    <p>That rules out the per-word tap-to-mark passage an app could offer (a 60-word story would need 60 elements and there is no tap-on-text component). What fits is the pattern below: the counts as pre-filled numbers, the words the computer marked wrong as chips that start ticked (the coach unticks any the child actually read right), one radio-button question per comprehension item showing the question and what the child said, and a dropdown for the things the computer does not mark, such as first sounds and letters. Where the computer is not confident enough, the field arrives empty rather than pre-filled, and the coach fills it from memory or after replaying the note.</p>
  </div>
  <div class="cols3">
    <figure><img src="mockups/chat_cta.png" alt="The chat: Rumi sends the child card, the coach sends the voice note, Rumi replies with the form button"><figcaption>1 · The chat. Rumi sends the card, the coach records one voice note for the whole five minutes, Rumi replies within two minutes with its counts and the <em>فارم کھولیں</em> button. The same message shape the observation form uses today.</figcaption></figure>
    <figure><img src="mockups/flow_urdu.png" alt="Flow screen 1 of 3, Urdu: pre-filled counts, flagged-word chips, a radio-button comprehension question"><figcaption>2 · Screen 1 of 3, Urdu. The counts are pre-filled number boxes. The three words the computer heard wrong are ticked chips; untick one and it counts as right. Each story question shows the child's answer and three radio buttons. The green button saves this screen and moves to English.</figcaption></figure>
    <figure><img src="mockups/flow_maths.png" alt="Flow screen 3 of 3, maths: dropdowns, a number box and a camera photo picker"><figcaption>3 · Screen 3 of 3, maths. Number reading and the word problems are dropdowns, the timed sums a number box, and the photo picker opens the camera for the child's written answers. Submit ends the child and Rumi sends the next card.</figcaption></figure>
  </div>
  <div class="prose">
    <p>The full draft of the form, in the exact JSON format Meta accepts, is in the files section (<a href="harness/flow/egra-review-flow.json">egra-review-flow.json</a>). It uses only components that exist in Flow version 7.0, and every label is within Meta's length limits. The pictures above are drawn from that file's example data, not invented separately.</p>
    <p>Storage is unchanged from the observation form: the computer's answer is saved once and never changed (version 1); the form opens pre-filled from it; the coach's submission is saved as version 2 with a note of what changed, item by item, because we need to know exactly where the computer was wrong to improve it. Only the coach who did the assessment can submit it.</p>
  </div>
</section>
'''
s = s[:start] + new + s[end:]

s = s.replace('''    <li><div><strong>The checking screen.</strong> A form opens in WhatsApp showing the computer's marks for Ayesha, block by block: 31 words correct in 60 seconds, two of three questions right, and so on. The coach changes anything that looks wrong. Where the computer was unsure, the form says "listen and mark" with the clip attached, and the coach decides.</div></li>''',
'''    <li><div><strong>The checking screen.</strong> Rumi replies in the chat with its counts and a button that opens a WhatsApp form, pre-filled block by block: 31 words correct in 60 seconds, one of three questions right, and so on. The coach changes anything that looks wrong. Where the computer was unsure, the field arrives empty and the coach fills it, replaying their own voice note in the chat if they need to.</div></li>''')
s = s.replace('''appear as numbers on the checking screen; marks below it appear as "listen and mark".''',
              '''arrive pre-filled on the checking screen; marks below it arrive as empty fields the coach fills.''')

# drop the old phone-mockup CSS, add a three-column figure grid
s = re.sub(r'\n  \.phone\{.*?(?=\n  \.[a-z]|\n</style>)', '', s, count=1, flags=re.S)
s = s.replace('</style>', '''  .cols3{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin:18px 0}
  .cols3 figure{margin:0}
  .cols3 img{width:100%;border:1px solid var(--line);border-radius:18px;display:block}
  .cols3 figcaption{font-size:12.5px;color:var(--muted);margin-top:8px;line-height:1.5}
  @media (max-width:760px){.cols3{grid-template-columns:1fr}}
</style>''', 1)
open(p, 'w', encoding='utf-8').write(s)

# site builder: copy the mockup PNGs and the Flow JSON
p = 'build_site.py'; s = open(p).read()
if 'mockups' not in s:
    s = s.replace("    write(os.path.join(OUT, '.nojekyll'), '')", """    mk = os.path.join(ROOT, 'harness', 'mockups')
    if os.path.isdir(mk):
        os.makedirs(os.path.join(OUT, 'mockups'), exist_ok=True)
        for fn in ('chat_cta.png', 'flow_urdu.png', 'flow_maths.png'):
            if os.path.exists(os.path.join(mk, fn)):
                shutil.copy(os.path.join(mk, fn), os.path.join(OUT, 'mockups', fn))
    fj = os.path.join(ROOT, 'harness', 'flow', 'egra-review-flow.json')
    if os.path.exists(fj):
        os.makedirs(os.path.join(OUT, 'harness', 'flow'), exist_ok=True); shutil.copy(fj, os.path.join(OUT, 'harness', 'flow', 'egra-review-flow.json'))
    write(os.path.join(OUT, '.nojekyll'), '')""")
    open(p, 'w').write(s)
print('patched')
