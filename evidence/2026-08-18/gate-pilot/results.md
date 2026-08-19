| Model | Strategy | N | Strict pass (checker) | Robustness (adversarial) | Viol/100w | "Must" softened | Anchor breaks | Top violation types | Judge audit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude:claude-opus-5 | few_shot | 5 | 20% | n/a | 0.26 | 4 | 3 | fabricated_quote:6; paraphrased_anchor:2; missing_operative_deadline:1 | 2/4 pass |
| claude:claude-opus-5 | structured_cot | 5 | 0% | n/a | 0.44 | 3 | 1 | fabricated_quote:9; unearned_word:5; missing_scaffold:2 | 4/4 pass |
| claude:claude-opus-5 | zero_shot | 5 | 0% | n/a | 0.51 | 1 | 5 | unearned_word:9; fabricated_quote:5; paraphrased_anchor:3 | 3/4 pass |
