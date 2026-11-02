# How I work with AI

*Samuel Viciana · AI Forward Deployed Engineer · indigo.ai assignment, part 1*

I don’t guide the agent. **I put it on rails.** Claude Code writes most of the code; I decide what “done” means before it writes a line, and nothing it builds can move that line.

Also as a one-page PDF with the diagram: [English](docs/ai-workflow/AI_WORKFLOW-en.pdf) · [Español](docs/ai-workflow/AI_WORKFLOW-es.pdf) · [Italiano](docs/ai-workflow/AI_WORKFLOW-it.pdf).

```
I set the rails ──► Agent builds ──► Gate (make done) ──► pass: merge, deploy
goals · thresholds   branch · tests     reads every goal ──► fail: stop & ask → one decision log → I decide
sealed lock          first · evals                              ↺ back to the agent
Secrets in .env · Coolify · platform secrets, resolved server-side: the model never sees a key.
```

## My workflow

- **Rails first.** Each goal has a threshold, the command that measures it and the file it writes. A sha256 lock seals them and only I regenerate it: the agent reads goals, it cannot edit them.
- **One decision log.** If a goal misses after two measured attempts, or it needs money, a dependency, an outward action or a judgement, the agent stops, writes it down and asks me, with options and a recommendation.
- **Tests ≠ evals.** Ordinary backend code: tests first and a coverage gate. What a model consumes (tool descriptions, error bodies, the prompt) is measured with a model: 81 tool cases I reviewed by hand, 150 sentence→tool cases on a local model, platform simulations read against the data.
- **Designing for a model is different.** A backend is judged by its tests; an interface an LLM consumes is judged by what a model does with it. So every response says what it could not match (missing terms, over budget, out of stock with alternatives) and every error says how to fix the call.
- **Secrets never reach a model.** The agent never reads keys; client data reaches the model only through read-only tools or MCP.

## When it went wrong

- The platform imported each operation’s *summary*, not its *description*: the model got one-liners and lost the guidance, silently. Only running the agent on the platform showed it. Now I test on the real consumer, not just my harness.
- An LLM judge failed real products as “invented” three runs in a row: it could not see the catalogue. Patching criteria fail by fail did not converge; now the judge checks behaviour and contradictions, and I read every Fail against the data.
- MCP showed “Connected” while every call was a 401. A one-line request log showed the platform sending the secret’s name (19 chars) instead of the key (64). When a model-driven client fails quietly: instrument, don’t guess.

## In the room

I hold a position when the evidence comes from the client’s own data. I chose the model by a controlled test of five; two that led a public benchmark answered in the wrong language or leaked tool tokens. I show the transcript, not the benchmark. I change my mind when the client brings a constraint I didn’t have (cost, compliance, a system of record) or better evidence: I rerun the same test and record the decision and its reason. A threshold never moves to make a result pass.

> Engineering is added value. SpaceX’s value isn’t metal and fuel; it’s how hard it is to turn them into a rocket that comes back. Models are my raw material. My job is the hard part around them: using tools like Claude Code professionally, securely and continuously. Not guided: on rails.
