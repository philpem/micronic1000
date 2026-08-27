# OpenCode configuration

`opencode.json` is strict JSON, so it cannot contain comments. This file records
the reasons behind the non-obvious model and agent settings.

## Model selection

The top-level default is `openrouter/deepseek/deepseek-v4-pro`. The utility model and
routine `general`/`docs` work use free OpenCode models to limit paid and
subscription usage.

`investigate` intentionally has **no `model` entry and no `temperature`**. An
OpenCode subagent without a model inherits the invoking primary session's live
model selection, including a choice made with `/model` or the model-selection
key binding. Omitting temperature also allows it to inherit models that do not
accept that parameter.

`investigate_deep` is pinned to `anthropic/claude-opus-5`; its OpenRouter
fallback is pinned to DeepSeek V4 Pro. `annotate` is pinned to DeepSeek V4
Flash because Ghidra writes are mechanical but consequential.

## Independent review

Consequential findings are reviewed by a different model family before they
are sent to `annotate`:

| Producer | Reviewer |
| --- | --- |
| Anthropic | `review_openai` (GPT-5.6 Sol) |
| OpenAI | `review_anthropic` (Claude Opus 5) |
| DeepSeek/OpenRouter | `review_anthropic` (Claude Opus 5) |

`review_openrouter_fallback` is an availability fallback, not an independent
vote. Model agreement never replaces byte-level adjudication by the parent.

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
cross-model fallback. The parent retries a subscription-backed deep
investigator or reviewer with its OpenRouter fallback only for authentication,
quota/rate-limit, timeout, provider-outage, model-unavailability, or 5xx
failures. It must not use fallback to hide weak reasoning, refusals,
context-length errors, malformed requests, or tool/schema errors.

If the primary session model selected with `/model` is itself unavailable, it
cannot orchestrate its own fallback. Select `openrouter/deepseek/deepseek-v4-pro`
manually and retry the prompt.

## Ghidra safety

Investigation and review agents are read-only in both their prompts and their
configured permissions. `annotate` is the only specialized Ghidra writer. Run
only one Ghidra-writing agent at a time, save after each successful batch, and
never use `clear_flow_and_repair` without the repository's documented
diff-guard procedure.
