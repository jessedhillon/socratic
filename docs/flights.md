# Flights

Flights track prompt experiments. A flight is a rendered template instance with
metadata about what was varied, what the inputs were, and what happened.

## `context` vs `feature_flags`

When creating a flight, callers provide two dicts: `context` and
`feature_flags`. Both are available during template rendering, but they serve
different purposes and occupy different namespaces.

### `context` — the task definition

Context describes _what_ is being done. It answers the question: what assessment
is this? What objective, what rubric, what prompts?

Context variables are top-level in the template namespace:

```jinja
{{ objective_title }}
{% for criterion in rubric_criteria %}
```

If you change the context, you're doing a different task.

### `feature_flags` — the experimental knobs

Feature flags describe _how_ the prompt behaves. They're the independent
variables in an experiment: tone, policy toggles, strategy switches.

Feature flags live under the `feature` namespace in the template:

```jinja
{% if feature.conviviality == "formal" %}
```

If you change feature flags, you're doing the same task differently.

### The A/B test framing

If you're running an experiment, feature flags are what differ between variant A
and variant B. Context stays the same across variants.

### Where the line gets blurry

The distinction is about _intent_, not _nature_. Something like
`time_budget_minutes` is context today (it's part of the task definition), but
could become a feature flag if you wanted to experiment with different time
budgets. `initial_prompts` could be a feature flag if you're testing different
conversation starters.

As a guide: if you're intentionally varying it across flights to measure its
effect on outcomes, it's a feature flag. If it defines the task and is held
constant within an experiment, it's context. When in doubt, ask: "would I want
to filter/group flights by this variable to compare outcomes?" If yes, it's
probably a feature flag.

### Rendering mechanics

The flights API builds the template render context as:

```python
render_context = {"feature": request.feature_flags, **request.context}
```

This means context keys must not collide with `feature`. Template authors should
use `feature.*` for anything experimental to make it visually obvious which
parts of a prompt are knobs vs. givens.
