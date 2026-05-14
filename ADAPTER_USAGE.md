# Reusable Bot Adapter Pattern

This runtime uses a pluggable adapter contract so tester/optimizer agents can be reused across projects.

## Contract

- File: `agents/bot_adapters.py`
- Interface shape:
  - `ask(question: str) -> BotReply`
  - `BotReply.text`: normalized answer text
  - `BotReply.raw`: original payload for debugging

## Current adapter

- `OpenClawQABotAdapter` calls local `Orchestrator().qa_run(question)`.

## Reuse in another project

1. Copy:
   - `agents/tester_agent.py`
   - `agents/optimizer_agent.py`
   - `bot_eval_pipeline.py`
2. Implement a project-specific adapter with the same `ask()` signature.
3. Replace `OpenClawQABotAdapter` import in `bot_eval_pipeline.py` with your adapter.
4. Run:
   - `python3 bot_eval_pipeline.py --bot-name "<your-bot>" --expected-prefix "<prefix>"`

## Notes

- Optimizer prefix check is configurable via `--expected-prefix`.
- Keep adapter thin; put business logic in your bot runtime, not in evaluator.
