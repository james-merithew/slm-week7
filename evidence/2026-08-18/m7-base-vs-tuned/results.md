| Model | Strategy | N | Strict pass (checker) | Robustness (adversarial) | Viol/100w | "Must" softened | Anchor breaks | Top violation types | Judge audit |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hf:/vol/runs/20260818-220624-N123-seed3407/adapter | zero_shot | 10 | 20% | n/a | 0.51 | 33 | 9 | missing_operative_deadline:7; missing_scaffold:5; unearned_word:5 | 0/1 pass |
| hf:Qwen/Qwen3-4B-Instruct-2507 | zero_shot | 10 | 0% | n/a | 0.87 | 3 | 11 | unearned_word:18; missing_operative_deadline:6; fabricated_quote:5 | 0/1 pass |
