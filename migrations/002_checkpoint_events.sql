-- Checkpoint events reuse the existing events table.
-- EventType.CHECKPOINT payloads store goal, step, state, and observations.
-- No schema change is required beyond documenting the new event_type value.

-- Example payload_json for event_type='checkpoint':
-- {
--   "goal": "...",
--   "step": 2,
--   "state": "acting",
--   "observations": [{"observation_id": "...", "source": "user", "content": "...", "metadata": {}}]
-- }

SELECT 1;
