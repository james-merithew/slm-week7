| Model | Strategy | N | Strict pass (checker) | Robustness (adversarial) | Viol/100w | "Must" softened | Anchor breaks | Top violation types | Judge audit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| mistral:mistral-large-latest | few_shot | 32 | 6% | 0% | 0.94 | 26 | 41 | fabricated_quote:43; unearned_word:37; missing_operative_deadline:25 | 4/6 pass |
| mistral:mistral-large-latest | structured_cot | 32 | 6% | 25% | 0.98 | 27 | 45 | unearned_word:35; missing_operative_deadline:23; paraphrased_anchor:22 | 3/6 pass |
| mistral:mistral-large-latest | zero_shot | 32 | 6% | 12% | 1.19 | 30 | 69 | paraphrased_anchor:44; unearned_word:40; fabricated_quote:25 | 3/6 pass |
