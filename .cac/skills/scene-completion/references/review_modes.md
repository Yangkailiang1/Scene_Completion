# Concern review modes

`review-concerns` supports three review entry modes and one result-import mode:

- `external`: call the configured OpenAI-compatible endpoint only. Missing configuration/key is an error; failed exchanges remain pending.
- `agent`: make no network request. Write one JSON packet per pending SSD exchange for the current Agent to review.
- `auto`: use the external endpoint when configuration is available. If configuration/key is unavailable, export every pending exchange for Agent review. If individual external batches fail, export only those still-pending exchanges.
- `merge-agent`: validate and merge Agent-produced judgements into pending matrix rows. Partial imports are allowed to support continuation; omitted batches remain pending.

## Agent handoff

The packet directory contains `manifest.json` plus one `batch-<stable-hash>.json` per exchange. Each packet includes only that exchange's use-case context, request/response, matching API contracts, routed concern knowledge, candidate records, safety instructions, and a result contract. These files contain project requirements and interface details; keep the directory local and protected.

For each batch, the Agent must return every listed `concern_key` exactly once and preserve the `exchange_id`. Valid statuses are `applicable`, `not_applicable`, and `needs_requirement`. Every record needs a concrete `basis`, non-empty `evidence_types`, and a `findings` array. `applicable` requires atomic findings; the other statuses prohibit findings. Findings need exception type/description, trigger, scenario steps, and recovery. Timeout impacts follow the existing `common.timeout` evidence rules.

Collect results as:

```json
{
  "batches": [
    {
      "exchange_id": "EXCH-001",
      "items": [
        {
          "concern_key": "common.timeout",
          "status": "needs_requirement",
          "basis": "需求没有给出可判断的时限或超时影响证据。",
          "evidence_types": ["requirement", "ssd"],
          "requirement_impact": "",
          "subsequent_behavior_impact": "",
          "environment_coordination_impact": "",
          "findings": []
        }
      ]
    }
  ]
}
```

Import with `--mode merge-agent --agent-results <results.json>`. The importer rejects unknown or duplicate exchanges, duplicate/extra/missing keys within a submitted exchange, invalid statuses, empty evidence, and malformed findings. It updates only pending rows, so already reviewed external batches cannot be overwritten accidentally. Repeat with the resulting matrix and more batch results until no candidates remain pending, then run `validate-concerns --require-complete` and `audit-run`.

`auto` is an orchestration handoff, not a hidden model call: the CLI emits packets and leaves them pending; the active Scene Completion Agent must review those packets and import its judgements. Never treat packet generation as a review decision or bypass the strict audit before assembly.
