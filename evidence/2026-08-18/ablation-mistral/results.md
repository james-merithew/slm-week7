| Model | Strategy | N | Strict pass (checker) | Robustness (adversarial) | Viol/100w | "Must" softened | Anchor breaks | Top violation types | Judge audit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mistral:mistral-large-latest | few_shot | 29 | 0% | 0% | 0.98 | 21 | 41 | fabricated_quote:42; unearned_word:28; missing_operative_deadline:25 | 4/6 pass |
| mistral:mistral-large-latest | structured_cot | 28 | 4% | 17% | 1.08 | 26 | 45 | unearned_word:32; missing_operative_deadline:23; paraphrased_anchor:22 | 2/5 pass |
| mistral:mistral-large-latest | zero_shot | 29 | 7% | 17% | 1.19 | 22 | 63 | paraphrased_anchor:40; unearned_word:38; fabricated_quote:24 | 3/6 pass |
