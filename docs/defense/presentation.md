# Speaker Script — Architecture Defense (Week 7)

> ~4.5 minutes. Present from the defense page; this is what you say.
> `[N]` = filled from the ablation run before the defense.
> Locked context: benefits notices, explained — adult English readers and
> intermediate-ESL, typed text v1. Base list: NGSL (~2,800 word families).

---

## Opening — 20 seconds

"I'm building a reading companion for benefits notices — the letters that
decide your food money, your health coverage, your rent.

It quotes the letter's exact words, then explains them in roughly the 2,800
words an adult reader already has. Every date, amount, and phone number comes
straight from the letter, character for character. 'Must' stays 'must.' And I
can prove all of it, on any conversation, with a script anyone in this room
can run."

## Beat 1 — The problem, measured — 60 seconds

"This isn't a felt problem — it's a documented one. About 88 percent of
benefits notices are written above the reading level of the people they're
sent to. When one program simplified its mailings in a randomized trial,
enrollment roughly doubled — the paperwork was the barrier, not the program.
The government grades its own plain writing at about a C.

And frontier models don't fix this — they make a new mistake. I measured two
frontier families, three prompting styles each, thirty notice conversations
per cell, with the full spec in the prompt. They still normalize dates,
reformat amounts, paraphrase form names — and they soften the modals. 'You
must submit this form' becomes 'you'll want to get that in.' That's RLHF
politeness working against the reader. Best first-pass strict compliance any
prompt could reach: [N] percent. First pass is the metric — no regeneration
credit. You can't prompt this away — you have to train it in."

## Beat 2 — How I chose this — 40 seconds

"I didn't guess my way here — twice. Eleven candidate behaviors went through
nine adversarial reviews over three rounds, and the earned-words rule won —
the runner-up is my written-down fallback. Then sixteen deployment contexts
went through the same gauntlet: discovery agents, domain experts, a red team,
a final three-lens ruling under my own criteria — spiky, usable, documented
harm. Fitness, banking, and patient health were killed. Government mail went
to the roadmap. And developer docs — my own favorite — lost under all three
of my own criteria. I'd rather lose my favorite than my discipline."

## Beat 3 — The rule — 60 seconds

"The behavior is one rule with teeth: quote, then explain — and never spend a
word the reader hasn't earned.

The companion quotes the operative line of the letter verbatim. Then it
explains it inside the reader's vocabulary — about 2,800 word families, the
published list — teaching at most two new words per turn, each with a plain
definition. Every date, amount, and contact must be an exact substring of the
letter; the checker rejects anything else. Modals are preserved — 'must' is
never softened, and 'may' never hardens into 'must.' It never gives advice:
ask 'should I appeal?' and you get the letter's own printed options and a
fixed referral to free legal aid. Every answer lands in three parts — what
this letter says, what it asks you to do, and by when.

One honest boundary: I claim the behavior, not the outcome. I don't promise
this saves anyone's benefits. It's harm-bounded by design — the baseline it
competes with is an unread letter."

## Beat 4 — The plan — 50 seconds

"The dataset is the curriculum. Synthetic notices — no real letters, no PII —
seeded from the variety of real formats. A frontier model writes the
explanations, and every one must pass the checker before it enters training:
quotes exact substrings of the source, anchors verbatim, modals intact,
vocabulary in bounds. Off-spec gets sent back and rewritten. So the training
data is on-spec by construction.

Then I train a small model on those lessons — four billion parameters — at
five dataset sizes, from 75 lessons up to 1,200. That answers the week's real
question: how little data does it take to hold this conjunction?

One deterministic script does all of it: filters the data, grades every
model, scores the staff's hidden test set. No LLM anywhere in the pass-fail
path."

## Beat 5 — The risks, before you ask — 45 seconds

"Four things I'll say before you do.

One: misbinding. The model can quote the right date and attach it to the
wrong obligation — and my checker can't see that. It's the residual risk. So
every eval scenario carries operative-deadline metadata, and a judge audits a
sample. I'm naming it before you find it.

Two: the modal check is crude — a global deterministic rule, no softeners on
obligations. That's stated on the slide, with the judge as audit only.

Three: scope. English-first, typed text, v1. Intermediate-ESL readers,
navigators, and family helpers are in scope today; other languages are
roadmap — the architecture is language-portable.

Four: compliance drifts over long exchanges — I chart it per turn, for every
model. And the pivot is pre-registered, same trigger as ever: if the best
prompt clears 85 percent, or my checker can't hit its false-positive bar
tonight, I switch to the banked fallback before any training spend."

## Close — 20 seconds

"Everyone fine-tunes a small model to add fluency. I fine-tuned a 4B to
refuse it — verbatim deadlines and unsoftened 'must's, inside a
2,800-word ceiling. Frontier models fail that conjunction precisely because
RLHF taught them to be gentle with the one word that keeps your benefits
alive. Every number is re-runnable by anyone in this room. Questions."

*(Q&A: dashboard on screen. Answers card: [qa-brief.md](qa-brief.md).)*

---

## If things break on the day

- **Run incomplete** → show the finished cells only, name the command that
  reproduces the rest. Never estimate a missing number aloud.
- **Live checker demo fails** → walk one pre-scored transcript by hand —
  notice on the left, explanation on the right, anchors matched line to line.
- **A ruling is challenged** → pull the published rule and show the path to the
  verdict. If it's genuinely ambiguous, log it as a spec issue in front of them.
- **Asked for a number we don't have** → "Not measured yet — it's on the
  requirements ledger for [checkpoint]."
