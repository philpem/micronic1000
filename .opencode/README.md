# OpenCode configuration

`opencode.json` is strict JSON, so it cannot contain comments. This file records
the reasons behind the non-obvious model and agent settings.

## Model selection

The top-level default is `openrouter/deepseek/deepseek-v4-pro`. The utility
model and routine `general`/`docs` work use free OpenCode models to limit paid
and subscription usage. DeepSeek through OpenRouter is metered, not free; the
default preserves subscription allowance at the cost of OpenRouter spend.

Choose the primary session model with `/model` or the model-selection key
binding. These are the recommended front-end choices:

| Workload | Primary model | Trade-off | Reviewer |
| --- | --- | --- | --- |
| Normal reverse-engineering work; preferred subscription balance | `anthropic/claude-sonnet-5` | Strong default while Anthropic allowance is available; preserves Opus usage | `review_openai` |
| Difficult, ambiguous, or cross-cutting analysis | `anthropic/claude-opus-5` | Highest-priority Anthropic choice; slower and consumes more allowance | `review_openai` |
| Normal work when using the OpenAI subscription | `openai/gpt-5.6-terra` | Balanced OpenAI alternative | `review_anthropic` |
| Difficult work needing an OpenAI frontier model | `openai/gpt-5.6-sol` | Accuracy-first OpenAI choice; use when the extra capability justifies its usage | `review_anthropic` |
| Preserve subscription allowance or recover from subscription unavailability | `openrouter/deepseek/deepseek-v4-pro` | Capable independent default, but incurs metered OpenRouter cost | `review_anthropic` |
| Lightweight coordination or clearly mechanical work | `anthropic/claude-fable-5` or `openai/gpt-5.6-luna` | Faster/lower-usage, but not the primary choice for consequential binary analysis | Reviewer matching the producer family |

Prefer Anthropic over OpenAI when both subscriptions are available because the
Anthropic subscription has the larger usable allowance. Reassess that ordering
if the providers' quotas change. The primary still owns evidence adjudication
and workflow control, so use Sonnet, Terra, or better whenever the prompt may
lead to consequential findings.

`investigate` intentionally has **no `model` entry and no `temperature`**. An
OpenCode subagent without a model inherits the invoking primary session's live
model selection, including a choice made with `/model` or the model-selection
key binding. Omitting temperature also allows it to inherit models that do not
accept that parameter.

`investigate_deep` is pinned to `anthropic/claude-opus-5`. Its first
availability fallback is `openai/gpt-5.6-sol`; its final fallback is
OpenRouter DeepSeek V4 Pro. `annotate` is pinned to DeepSeek V4 Flash because
Ghidra writes are mechanical but consequential.

## Independent review

Consequential findings are reviewed by a different model family before they
are sent to `annotate`:

| Producer | Reviewer |
| --- | --- |
| Anthropic | `review_openai` (GPT-5.6 Sol) |
| OpenAI | `review_anthropic` (Claude Opus 5) |
| DeepSeek/OpenRouter | `review_anthropic` (Claude Opus 5) |

`review_openrouter_fallback` is an availability fallback, not an independent
vote. It is independent for findings produced by Anthropic or OpenAI, but not
for findings produced by DeepSeek. If DeepSeek produced the finding and no
Anthropic or OpenAI reviewer is available, defer consequential annotation.
Model agreement never replaces byte-level adjudication by the parent.

Review is required for semantic renames, hardware identities, calling
conventions, computed table mappings, overturned findings, and promotion to
CONFIRMED. Routine searches, inventories, exact mechanical edits, and
documentation-only maintenance do not require frontier review.

The project uses a post-investigation review gate rather than an advisor agent:

1. `investigate` or `investigate_deep` produces provisional findings.
2. A reviewer from another family freshly checks the decisive evidence and
   seeks falsification.
3. The parent resolves disagreements by returning to the bytes.
4. `annotate` applies only the adjudicated safe scope and saves Ghidra.
5. `docs` updates the written record and rebuilds the site.

## Availability fallback

OpenCode currently assigns one model to an agent and does not provide native
cross-model fallback. For deep investigation, the parent retries the unchanged
task in this order:

1. `investigate_deep` — Claude Opus 5.
2. `investigate_deep_openai_fallback` — GPT-5.6 Sol.
3. `investigate_deep_openrouter_fallback` — DeepSeek V4 Pro.

Advance through the chain only for authentication, quota/rate-limit, timeout,
provider-outage, model-unavailability, or 5xx failures. A subscription-backed
reviewer uses `review_openrouter_fallback` for the same failures. Do not use
availability fallback to hide weak reasoning, refusals, context-length errors,
malformed requests, or tool/schema errors.

If the primary session model selected with `/model` is itself unavailable, it
cannot orchestrate its own fallback. Select `openrouter/deepseek/deepseek-v4-pro`
manually and retry the prompt.

## Ghidra safety

Investigation and review agents are read-only in both their prompts and their
configured permissions. `annotate` is the only specialized Ghidra writer. Run
only one Ghidra-writing agent at a time, save after each successful batch, and
never use `clear_flow_and_repair` without the repository's documented
diff-guard procedure.
