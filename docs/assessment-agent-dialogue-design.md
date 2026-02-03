# Assessment Agent Dialogue Design

This document captures the design intentions behind the Socratic assessment agent's conversational style and tone. It serves as a reference for future prompt tuning work.

## Design Philosophy

The assessment agent is a **Socratic interlocutor**, not an interviewer administering a checklist. Its purpose is to understand how the learner thinks about a topic — assessment is a consequence of that understanding, not the goal itself.

A successful conversation feels like a dialogue with a curious, engaged thinking partner. It should not feel like a structured interview where the agent checks boxes and moves on.

## Problems Identified

Analysis of early assessment transcripts revealed several anti-patterns:

### 1. The Validation Sandwich

Almost every agent response followed the same pattern:

1. "You've highlighted X / You've provided a thoughtful perspective on Y" (praise)
2. Brief elaboration
3. New question

This creates a **compliment-question loop** that feels mechanical. A real interlocutor would sometimes just ask the next question, or react with genuine curiosity ("Wait — seven years? That changes things") rather than summarizing what the learner said back to them in praise form.

**Root cause**: RLHF training pushes models toward validating user responses. The prompt must explicitly counter this tendency.

### 2. Breadth-First Exploration

The agent treated each response as sufficient evidence and moved on. Rich, layered answers that could sustain 3-4 exchanges were acknowledged once and then the agent pivoted to a new topic.

**Example**: A learner gave a nuanced answer about suspending modern morality when reading The Odyssey. Instead of pressing on that ("Where does that break down? What if Odysseus had done X?"), the agent validated and moved to a completely different area.

**Core issue**: The agent was breadth-first when it should be depth-first.

### 3. Not Actually Socratic

The agent rarely challenged the learner, surfaced tensions, or asked them to reconcile contradictions. When handed genuinely interesting contradictions (e.g., Odysseus as faithful-yet-unfaithful), the agent validated and moved on instead of pressing ("So is he faithful or not? Can those coexist?").

The probing guidance only triggered on weak answers. But the richest Socratic moments come from pressing on _strong_ answers — testing their edges, asking what would challenge them.

### 4. Interviewer-Driven Topic Transitions

Topic changes happened on the agent's schedule, not based on conversational flow. Transitions felt like "checking a box" rather than following the learner's thread.

### 5. Abrupt Closings with Factual Claims

The agent sometimes confirmed factual claims in the same breath as closing the conversation, violating the rule against indicating correctness.

## Design Decisions

### Depth Over Breadth (First-Class Principle)

Previously "depth is more valuable than coverage" was buried in the time management section. It's now a **top-level conversational priority**:

> Stay with a productive thread for multiple exchanges before moving on. A single idea explored thoroughly — with follow-ups, challenges, and elaboration — reveals far more than surveying many topics.
>
> Do not move to a new area after one exchange. If the learner gives a substantive answer, your next response should go deeper into that same idea, not pivot to something new.

### Probing Reframed

Probing now applies to **all substantive answers**, not just weak ones:

> Probe every substantive answer — not only weak ones. Strong answers deserve follow-ups that test their edges:
>
> - Ask for concrete examples or counterexamples
> - Ask them to explain _why_ or _how_ they think something works
> - Present a related situation and ask how their reasoning applies
> - Surface tensions, edge cases, or contradictions and ask them to reconcile
> - Ask what would change if a condition were different
>
> Stay with a thread for at least 3–4 exchanges before considering a move.

### Anti-Validation Rule

Explicit guidance against the validation sandwich:

> Do NOT begin responses by summarizing or praising what the learner just said. Respond directly — with a follow-up question, a challenge, or a new angle. Acknowledgment should be implicit in how you engage, not stated explicitly.

### Transition Guidance

Move to new areas only when threads are genuinely exhausted:

> Move to a new area only when the current thread is genuinely exhausted — the learner is repeating themselves, has nothing more to add, or signals readiness to move on. When you do transition, connect the new topic to something the learner already said rather than introducing it cold.

### Entry Points as Raw Material

Educator-provided prompts are suggestions, not a script:

> Treat these as raw material, not a script. You may use one directly, rephrase it, combine ideas from several, or craft your own opening based on the topic. Vary your approach — do not always lead with the first item on the list.

### Tone Levels

Four conviviality settings control the agent's interpersonal style:

| Level              | Description                                                                                                                     |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| **Formal**         | Strictly professional. Brief acknowledgments, efficient transitions.                                                            |
| **Professional**   | Polite and measured. Acknowledges when it helps flow.                                                                           |
| **Conversational** | Warm and natural. Uses learner's examples and wording. Feels organic.                                                           |
| **Collegial**      | Genuinely curious and engaged. Treats learner as thinking partner. Explores their scenarios. Shows enthusiasm without teaching. |

Default is **collegial** for most assessments.

## What We Chose Not to Change

### Farewell Behavior

When a learner raises a new detail in their final response, ideally the agent would engage with it before closing. However, implementing this correctly requires the farewell subagent to signal "conversation should continue" back to the caller — added complexity for marginal benefit. For now, it's acceptable for the agent to briefly acknowledge and close.

### Prescriptive Opening

We considered replacing the entry points with "Begin by asking what interests them most about the topic." This doesn't work well for all subjects ("What interests you most about ratios?"). Instead, we tell the agent to treat prompts as raw material and vary its approach.

## Measuring Success

A good assessment conversation exhibits:

1. **Natural flow** — transitions feel connected, not procedural
2. **Depth on threads** — at least some topics get 3+ exchanges
3. **Genuine probing** — follow-ups that test edges of strong answers
4. **No validation sandwiches** — responses don't open with praise/summary
5. **Learner-led direction** — agent follows interesting threads the learner introduces
6. **Appropriate challenge** — tensions and contradictions are surfaced, not glossed over

## Prompt Location

The system prompt lives at:

```
socratic/llm/prompts/agent/assessment_system.j2
```

It's a Jinja2 template that receives:

- `objective_title`, `objective_description` — the learning objective
- `rubric_criteria` — list of assessment dimensions
- `initial_prompts` — educator-provided entry points
- `conviviality` — tone setting enum
- `time_budget_minutes` — optional time constraint

## Related Files

- `socratic/llm/agent/assessment/farewell.py` — farewell subagent (default conviviality: collegial)
- `socratic/llm/agent/assessment/agent.py` — main assessment agent graph
- `socratic/llm/prompts/agent/assessment_farewell.j2` — farewell message template

### Few-Shot Example Files

The following example templates demonstrate the principles in practice. They are
conditionally included in the system prompt when `include_examples=True` (the default).

- `socratic/llm/prompts/agent/assessment_example_anti_validation.j2` — how to respond without the validation sandwich
- `socratic/llm/prompts/agent/assessment_example_depth.j2` — staying with threads for 3-4 exchanges
- `socratic/llm/prompts/agent/assessment_example_probing.j2` — probing strong answers, not just weak ones
- `socratic/llm/prompts/agent/assessment_example_transitions.j2` — natural, learner-connected transitions

To disable examples (reduces prompt length): set `include_examples=False` in the `AssessmentState`.

## Revision History

| Date       | Change                                                                                           | Ticket  |
| ---------- | ------------------------------------------------------------------------------------------------ | ------- |
| 2026-01-31 | Initial prompt tuning: depth-over-breadth, anti-validation, probing reframe, transition guidance | SOC-153 |
