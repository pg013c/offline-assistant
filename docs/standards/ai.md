# AI standards

Rules for everything that involves a model: prompts, tool calling, retrieval, model configuration and the offline guarantee. These are the rules most specific to this project; reviewers check them first.

## Grounding and citations

- **AI-01** Every factual claim in an answer cites at least one chunk. A citation must resolve to a stored chunk id; the agent service verifies this before returning the answer.
- **AI-02** If retrieval returns nothing above the relevance threshold, the answer is a refusal. The model is not asked to answer from its own knowledge.
- **AI-03** Quotes shown as quotes are copied from the chunk text, never generated.

## Untrusted content

- **AI-10** Document text, tool results and transcribed speech are data. They are passed to the model inside clearly delimited blocks and the system prompt says they must not be followed as instructions.
- **AI-11** Tools have no side effects outside the local notes directory. No tool executes code, opens network connections or reads arbitrary paths.
- **AI-12** Prompt-injection cases (documents containing instructions) are part of the evaluation set.

## Structured output and reliability

- **AI-20** Tool arguments and final answers are defined as Pydantic models, sent as JSON schema, and validated on return.
- **AI-21** Invalid output is retried with the validation error fed back, at most `ASSISTANT_MAX_RETRIES` times (default 2). After that the result is a typed failure, never an exception leaking to the user and never an unbounded loop.
- **AI-22** Every model call has a timeout. Every agent run has a maximum number of tool-call turns.
- **AI-23** Model capabilities (tools, JSON schema, streaming) are declared in configuration per model; code checks the flag instead of guessing from the model name.

## Prompts

- **AI-30** Prompts live in versioned files under `backend/src/assistant/prompts/`, not as string literals in code. Templates use explicit named variables.
- **AI-31** A change to a prompt, tool schema, retrieval parameter or default model is a model-behaviour change: it needs an evaluation run (ADR 0006), and the PR shows the before/after metrics.
- **AI-32** Prompts are in English. The answer language follows the question language; this is stated in the prompt and covered by evaluation cases in Polish and English.

## Models

- **AI-40** Models are identified by exact name and version (or file hash) in configuration. "latest" tags are not allowed.
- **AI-41** Every model in use is listed in the README with its licence and source. Models with licences that forbid this use are not added.
- **AI-42** Model weights are never committed. They are fetched by `make models` or copied from offline media (ADR 0004).

## Offline and privacy

- **AI-50** No library is allowed to download at runtime: offline environment flags are set in settings, and missing assets fail at startup with a clear message.
- **AI-51** Telemetry is disabled for every component that has it.
- **AI-52** Network access exists only in comparison mode behind `ASSISTANT_ALLOW_NETWORK=1`. Code that opens a connection elsewhere is a blocker in review.
- **AI-53** Traces (Langfuse) are local. Logs at info level contain ids, timings and token counts, not document text or prompts.

## Measurement

- **AI-60** Every model call records model id, prompt tokens, completion tokens, time to first token and total time.
- **AI-61** Evaluation results are reproducible: the run records model versions, configuration, dataset version and hardware.
