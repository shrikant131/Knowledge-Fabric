# Operator runbook

## Daily checks

- Review source errors.
- Check ingestion freshness.
- Review low-confidence query volume.
- Check provider health if LLM mode is enabled.
- Run the golden evaluation after deployments.

## Incident: source stopped updating

1. Inspect last run and error.
2. Test credentials.
3. Run manual sync.
4. Restart watcher if required.
5. Escalate persistent API failures.

## Incident: retrieval quality regression

1. Freeze the current configuration.
2. Run golden evaluation.
3. Compare retrieval traces with the last known-good configuration.
4. Check embedding/index compatibility.
5. Roll back configuration if required.
