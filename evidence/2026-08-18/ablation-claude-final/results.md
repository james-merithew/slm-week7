| Model | Strategy | N | Strict pass (checker) | Robustness (adversarial) | Viol/100w | "Must" softened | Anchor breaks | Top violation types | Judge audit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| claude:claude-opus-5 | few_shot | 32 | 16% | 38% | 0.30 | 38 | 12 | unearned_word:38; fabricated_quote:23; paraphrased_anchor:8 | 4/6 pass |
| claude:claude-opus-5 | structured_cot | 32 | 16% | 25% | 0.38 | 46 | 12 | unearned_word:42; fabricated_quote:22; missing_scaffold:8 | 4/6 pass |
| claude:claude-opus-5 | zero_shot | 32 | 6% | 12% | 0.40 | 54 | 16 | unearned_word:62; fabricated_quote:29; paraphrased_anchor:10 | 8/12 pass |
