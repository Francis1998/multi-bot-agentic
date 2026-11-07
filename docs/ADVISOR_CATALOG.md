# Advisor & Guard Catalog

Offline, HITL-safe advisors, guards, and limiters for multi-bot runs. They were moved here **verbatim**
from the former README so the README can stay a short showcase. Each entry links to its guide in
[`docs/guides/`](guides/) and its demo GIF in [`assets/demo/`](../assets/demo/).

> **Model names in these entries are historical.** Entries such as `Stack: GPT-5.5 / Claude Sonnet 4.6 /
> Gemini 3.x / Kimi K2` name the models that were current when each entry was written. The verified
> current stack is in [Configuration › Current Model Stack](CONFIGURATION.md#current-model-stack).

**Adding an entry:** add new advisor, guard, or limiter entries **here, not in the README**. Use a
`### ClassName` heading, a demo GIF, a one-paragraph summary, and a link to the guide.

## Demo gallery

![DeadLetterToolQueue](../assets/demo/dead-letter-tool-queue.gif)

![BotHandoffReceiptStore](../assets/demo/bot-handoff-receipt.gif)

![ToolCallQuotaGuard](../assets/demo/tool-call-quota-guard.gif)
![BotTurnFairnessScheduler](../assets/demo/bot-turn-fairness-scheduler.gif)
![HitlEscalationCooldownGate](../assets/demo/hitl-escalation-cooldown-gate.gif)
![BotRoleConflictDetector](../assets/demo/bot-role-conflict-detector.gif)
![PlanStepDependencyResolver](../assets/demo/plan-step-dependency-resolver.gif)
![BlackboardEntryTtlEvictor](../assets/demo/blackboard-entry-ttl-evictor.gif)
![BotHeartbeatLivenessWatchdog](../assets/demo/bot-heartbeat-liveness-watchdog.gif)
![SharedBlackboardWriteLease](../assets/demo/shared-blackboard-write-lease.gif)
![FanInBarrierGate](../assets/demo/fan-in-barrier-gate.gif)
![ToolCallWaveScheduler](../assets/demo/tool-call-wave-scheduler.gif)
![DeterministicRunSeedGuard](../assets/demo/deterministic-run-seed-guard.gif)
![CriticPassBudgetLimiter](../assets/demo/critic-pass-budget-limiter.gif)
![VoteTieBreakPolicy](../assets/demo/vote-tie-break-policy.gif)
![BotSpawnBudgetLimiter](../assets/demo/bot-spawn-budget-limiter.gif)
![AgentHandoffDepthLimiter](../assets/demo/agent-handoff-depth-limiter.gif)
![ConsensusQuorumFloorGuard](../assets/demo/consensus-quorum-floor-guard.gif)
![OrchestratorStallWatchdog](../assets/demo/orchestrator-stall-watchdog.gif)
![PlannerReplanBudgetLimiter](../assets/demo/planner-replan-budget-limiter.gif)
![SharedMemoryConflictBandGuard](../assets/demo/shared-memory-conflict-band-guard.gif)
![ToolResultPiiRedactionGate](../assets/demo/tool-result-pii-redaction-gate.gif)
![ToolResultSchemaHashGate](../assets/demo/tool-result-schema-hash-gate.gif)
![FanInSkewBandGuard](../assets/demo/fan-in-skew-band-guard.gif)
![ToolInvocationDeadlineGuard](../assets/demo/tool-invocation-deadline-guard.gif)
![CriticTimeoutBandGuard](../assets/demo/critic-timeout-band-guard.gif)
![BlackboardWriteAmplificationBandGuard](../assets/demo/blackboard-write-amplification-band-guard.gif)
![CriticAgreementEntropyGate](../assets/demo/critic-agreement-entropy-gate.gif)
![MultiBotLatencyBudgetAllocator](../assets/demo/multi-bot-latency-budget-allocator.gif)
![ToolResultCardinalityGate](../assets/demo/tool-result-cardinality-gate.gif)
![CriticPairwiseKappaGate](../assets/demo/critic-pairwise-kappa-gate.gif)
![ToolSandboxCpuQuotaGuard](../assets/demo/tool-sandbox-cpu-quota-guard.gif)
![CriticLatencySloBandGuard](../assets/demo/critic-latency-slo-band-guard.gif)
![CriticSelfConsistencyBandGuard](../assets/demo/critic-self-consistency-band-guard.gif)
![OrchestratorCascadeFailureAdvisor](../assets/demo/orchestrator-cascade-failure-advisor.gif)
![MessageBusBackpressureAdvisor](../assets/demo/message-bus-backpressure-advisor.gif)
![BlackboardStaleEntryAdvisor](../assets/demo/blackboard-stale-entry-advisor.gif)
![PlannerDepthCapAdvisor](../assets/demo/planner-depth-cap-advisor.gif)
![BotCapabilityDriftAdvisor](../assets/demo/bot-capability-drift.gif)
![ConsensusQuorumBandGuard](../assets/demo/consensus-quorum-band.gif)
![PlanStepCycleDetectorGuard](../assets/demo/plan-step-cycle-detector.gif)
![AgentHandoffLatencyAdvisor](../assets/demo/agent-handoff-latency.gif)
![SharedMemoryPoisoningGuard](../assets/demo/shared-memory-poisoning.gif)
![ToolResultPoisoningGuard](../assets/demo/tool-result-poisoning.gif)
![ToolRetryBudgetBandGuard](../assets/demo/tool-retry-budget-band-guard.gif)
![CriticTokenBudgetBandGuard](../assets/demo/critic-token-budget-band-guard.gif)
![ToolSandboxDiskQuotaGuard](../assets/demo/tool-sandbox-disk-quota-guard.gif)
![OrchestratorFairnessAgingAdvisor](../assets/demo/orchestrator-fairness-aging-advisor.gif)
![PlannerCostCeilingAdvisor](../assets/demo/planner-cost-ceiling-advisor.gif)
![ToolSandboxMemoryQuotaGuard](../assets/demo/tool-sandbox-memory-quota-guard.gif)
![SharedMemoryTtlEvictionAdvisor](../assets/demo/shared-memory-ttl-eviction-advisor.gif)
![PlannerBeamWidthLimiter](../assets/demo/planner-beam-width-limiter.gif)
![ToolSandboxEgressClassGuard](../assets/demo/tool-sandbox-egress-class-guard.gif)
![PlannerGoalDriftGuard](../assets/demo/planner-goal-drift-guard.gif)
![ConsensusTimeoutBandGuard](../assets/demo/consensus-timeout-band-guard.gif)

![CriticVerdictDiversityGate](../assets/demo/critic-verdict-diversity-gate.gif)
![ToolArgByteBudgetGuard](../assets/demo/tool-arg-byte-budget-guard.gif)
![SharedMemoryQuotaGuard](../assets/demo/shared-memory-quota-guard.gif)
![DebateRoundLimiter](../assets/demo/debate-round-limiter.gif)
![ConsensusConfidenceBandAdvisor](../assets/demo/consensus-confidence-band-advisor.gif)
![ToolResultFingerprintDeduper](../assets/demo/tool-result-fingerprint-deduper.gif)
![BotSkillTagRouter](../assets/demo/bot-skill-tag-router.gif)
![SessionTokenBudgetLedger](../assets/demo/session-token-budget-ledger.gif)
![BotVoteConsensusAggregator](../assets/demo/bot-vote-consensus-aggregator.gif)
![SessionTtlExpirer](../assets/demo/session-ttl-expirer.gif)
![ToolCallLatencyTracker](../assets/demo/tool-call-latency-tracker.gif)
![CriticBotVerdictGate](../assets/demo/critic-bot-verdict.gif)
![ConversationTurnBudgetGuard](../assets/demo/conversation-turn-budget.gif)
![ToolPermissionAllowlist](../assets/demo/tool-permission-allowlist.gif)
![StickyBotAffinityStore](../assets/demo/sticky-bot-affinity.gif)
![RunDeadlineWatchdog](../assets/demo/run-deadline-watchdog.gif)
![ToolCallIdempotencyCache](../assets/demo/tool-call-idempotency-cache.gif)

## Entries

### ToolSandboxNetworkExfilGuard

![ToolSandboxNetworkExfilGuard](../assets/demo/tool-sandbox-network-exfil-guard.gif)

Offline HITL exfil_score bands. Gap vs AutoGen/CrewAI/LangGraph tool-sandbox network-exfil guards. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/TOOL_SANDBOX_NETWORK_EXFIL_GUARD_GUIDE.md`.
### AgentDeadlockDetectorGuard

![AgentDeadlockDetectorGuard](../assets/demo/agent-deadlock-detector-guard.gif)

Offline HITL deadlock_score bands. Gap vs AutoGen/CrewAI/LangGraph agent-deadlock detectors. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/AGENT_DEADLOCK_DETECTOR_GUARD_GUIDE.md`.

### PromptLeakBandAdvisor

![PromptLeakBandAdvisor](../assets/demo/prompt-leak-band-advisor.gif)

Offline HITL leak_score bands. Gap vs AutoGen/CrewAI/LangGraph prompt-leak band advisors. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/PROMPT_LEAK_BAND_ADVISOR_GUIDE.md`.

### ToolArgSchemaDriftGuard

![ToolArgSchemaDriftGuard](../assets/demo/tool-arg-schema-drift.gif)

Offline HITL schema_drift_score bands. Gap vs AutoGen/CrewAI/LangGraph tool-argument schema-drift guards. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/TOOL_ARG_SCHEMA_DRIFT_GUARD_GUIDE.md`.

### PlannerStepBudgetBandAdvisor

![PlannerStepBudgetBandAdvisor](../assets/demo/planner-step-budget-band.gif)

Offline HITL steps_used_ratio bands. Gap vs LangGraph/CrewAI/AutoGen planner step-budget monitors. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/PLANNER_STEP_BUDGET_BAND_ADVISOR_GUIDE.md`.

### ToolSandboxSyscallDenylistGuard

![ToolSandboxSyscallDenylistGuard](../assets/demo/tool-sandbox-syscall-denylist.gif)

Offline HITL denied_syscall_rate bands. Gap vs AutoGen/CrewAI/LangGraph tool-sandbox syscall denylist guards. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/TOOL_SANDBOX_SYSCALL_DENYLIST_GUARD_GUIDE.md`.

### BlackboardCasWriteSkewGuard

![BlackboardCasWriteSkewGuard](../assets/demo/blackboard-cas-write-skew.gif)

Offline HITL write_skew_score bands. Gap vs AutoGen/CrewAI/LangGraph shared-blackboard CAS/write-skew guards. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/BLACKBOARD_CAS_WRITE_SKEW_GUARD_GUIDE.md`.
### PlannerHorizonBandAdvisor

![PlannerHorizonBandAdvisor](../assets/demo/planner-horizon-band.gif)

Offline HITL horizon_steps_ratio bands. Gap vs LangGraph/CrewAI/AutoGen planner-horizon monitors. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/PLANNER_HORIZON_BAND_ADVISOR_GUIDE.md`.

### CriticQuorumHysteresisAdvisor

![CriticQuorumHysteresisAdvisor](../assets/demo/critic-quorum-hysteresis.gif)

Offline HITL advisor for `hysteresis_score` bands. Gap vs AutoGen/CrewAI/LangGraph critic-quorum hysteresis monitors. Optional polish via GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.

### OrchestratorFanoutBudgetBandAdvisor

![OrchestratorFanoutBudgetBandAdvisor](../assets/demo/orchestrator-fanout-budget-band.gif)

Offline HITL advisor for `fanout_ratio` bands. Gap vs AutoGen/CrewAI/LangGraph orchestrator fan-out budget monitors. Optional polish via GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.

### SubgraphRecursionCapAdvisor

![SubgraphRecursionCapAdvisor](../assets/demo/subgraph-recursion-cap.gif)

Offline HITL advisor for `recursion_depth_ratio` bands. Gap vs LangGraph/CrewAI subgraph recursion-cap monitors. Optional polish via GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.

### WorkerStarvationBandAdvisor

![WorkerStarvationBandAdvisor](../assets/demo/worker-starvation-band.gif)

Offline HITL `starvation_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen worker-starvation band monitors. See `docs/guides/WORKER_STARVATION_BAND_ADVISOR_GUIDE.md`.

### ToolPermissionDriftAdvisor

![ToolPermissionDriftAdvisor](../assets/demo/tool-permission-drift.gif)

Offline HITL `drift_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen tool-permission drift monitors. See `docs/guides/TOOL_PERMISSION_DRIFT_ADVISOR_GUIDE.md`.

### BlackboardLeaseThrashAdvisor

![BlackboardLeaseThrashAdvisor](../assets/demo/blackboard-lease-thrash.gif)

Offline HITL `thrash_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen blackboard lease-thrash monitors. See `docs/guides/BLACKBOARD_LEASE_THRASH_ADVISOR_GUIDE.md`.

### SharedKvWriteAmplificationAdvisor

![SharedKvWriteAmplificationAdvisor](../assets/demo/shared-kv-write-amplification.gif)

Offline HITL `write_amp_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen shared-KV write-amplification monitors. See `docs/guides/SHARED_KV_WRITE_AMPLIFICATION_ADVISOR_GUIDE.md`.

### HandoffPayloadBloatAdvisor

![HandoffPayloadBloatAdvisor](../assets/demo/handoff-payload-bloat.gif)

Offline HITL `payload_bloat_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen handoff payload-bloat monitors. See `docs/guides/HANDOFF_PAYLOAD_BLOAT_ADVISOR_GUIDE.md`.

### SupervisorIdleSkewAdvisor

![SupervisorIdleSkewAdvisor](../assets/demo/supervisor-idle-skew.gif)

Offline HITL `idle_skew_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen supervisor idle-skew monitors. See `docs/guides/SUPERVISOR_IDLE_SKEW_ADVISOR_GUIDE.md`.

### BlackboardReadStalenessAdvisor

![BlackboardReadStalenessAdvisor](../assets/demo/blackboard-read-staleness.gif)

Offline HITL `staleness_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen blackboard read-staleness monitors. See `docs/guides/BLACKBOARD_READ_STALENESS_ADVISOR_GUIDE.md`.

### ToolSideEffectReplayBandAdvisor

![ToolSideEffectReplayBandAdvisor](../assets/demo/tool-side-effect-replay-band.gif)

Offline HITL `replay_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen tool side-effect replay monitors. See `docs/guides/TOOL_SIDE_EFFECT_REPLAY_BAND_ADVISOR_GUIDE.md`.

### CriticFanoutSkewAdvisor

![CriticFanoutSkewAdvisor](../assets/demo/critic-fanout-skew.gif)

Offline HITL `skew_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen critic-fanout skew monitors. See `docs/guides/CRITIC_FANOUT_SKEW_ADVISOR_GUIDE.md`.

### SharedLockContentionBandAdvisor

![SharedLockContentionBandAdvisor](../assets/demo/shared-lock-contention-band.gif)

Offline HITL `contention_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen shared-lock contention monitors. See `docs/guides/SHARED_LOCK_CONTENTION_BAND_ADVISOR_GUIDE.md`.

### ConsensusQuorumStallAdvisor

![ConsensusQuorumStallAdvisor](../assets/demo/consensus-quorum-stall.gif)

Offline HITL `stall_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen consensus quorum-stall monitors. See `docs/guides/CONSENSUS_QUORUM_STALL_ADVISOR_GUIDE.md`.

### CriticMajorityCaptureBandAdvisor

![CriticMajorityCaptureBandAdvisor](../assets/demo/critic-majority-capture.gif)

Offline HITL `capture_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen critic majority-capture monitors. See `docs/guides/CRITIC_MAJORITY_CAPTURE_BAND_ADVISOR_GUIDE.md`.

### AgentHandoffLoopBandAdvisor

![AgentHandoffLoopBandAdvisor](../assets/demo/agent-handoff-loop.gif)

Offline HITL `loop_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen agent handoff-loop monitors. See `docs/guides/AGENT_HANDOFF_LOOP_BAND_ADVISOR_GUIDE.md`.

### WorkerHeartbeatMissBandAdvisor

![WorkerHeartbeatMissBandAdvisor](../assets/demo/worker-heartbeat-miss.gif)

Offline HITL `miss_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen worker heartbeat-miss monitors. See `docs/guides/WORKER_HEARTBEAT_MISS_BAND_ADVISOR_GUIDE.md`.

### SupervisorRestartThrashAdvisor

![SupervisorRestartThrashAdvisor](../assets/demo/supervisor-restart-thrash.gif)

Offline HITL `restart_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen supervisor restart-thrash monitors. See `docs/guides/SUPERVISOR_RESTART_THRASH_ADVISOR_GUIDE.md`.

### ToolResultSchemaDriftBandAdvisor

![ToolResultSchemaDriftBandAdvisor](../assets/demo/tool-result-schema-drift-band.gif)

Offline HITL `drift_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen tool-result schema-drift monitors. See `docs/guides/TOOL_RESULT_SCHEMA_DRIFT_BAND_ADVISOR_GUIDE.md`.

### SubgraphCancelLeakAdvisor

![SubgraphCancelLeakAdvisor](../assets/demo/subgraph-cancel-leak.gif)

Offline HITL `leak_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen subgraph cancel-leak monitors. See `docs/guides/SUBGRAPH_CANCEL_LEAK_ADVISOR_GUIDE.md`.

### PlannerToolMismatchBandAdvisor

![PlannerToolMismatchBandAdvisor](../assets/demo/planner-tool-mismatch-band.gif)

Offline HITL `mismatch_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen planner-tool mismatch monitors. See `docs/guides/PLANNER_TOOL_MISMATCH_BAND_ADVISOR_GUIDE.md`.

### OrchestratorHeartbeatGapAdvisor

![OrchestratorHeartbeatGapAdvisor](../assets/demo/orchestrator-heartbeat-gap.gif)

Offline HITL `heartbeat_gap_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen orchestrator heartbeat monitors. See `docs/guides/ORCHESTRATOR_HEARTBEAT_GAP_ADVISOR_GUIDE.md`.

### FanInBarrierStallAdvisor

![FanInBarrierStallAdvisor](../assets/demo/fan-in-barrier-stall.gif)

Offline HITL `stall_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen fan-in barrier stall monitors. See `docs/guides/FAN_IN_BARRIER_STALL_ADVISOR_GUIDE.md`.

### AgentLoopTokenBleedAdvisor

![AgentLoopTokenBleedAdvisor](../assets/demo/agent-loop-token-bleed.gif)

Offline HITL `token_bleed_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen agent-loop token-bleed monitors. See `docs/guides/AGENT_LOOP_TOKEN_BLEED_ADVISOR_GUIDE.md`.

### PlannerCriticOscillationBandAdvisor

![PlannerCriticOscillationBandAdvisor](../assets/demo/planner-critic-oscillation-band.gif)

Offline HITL `oscillation_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen planner-critic oscillation monitors. See `docs/guides/PLANNER_CRITIC_OSCILLATION_BAND_ADVISOR_GUIDE.md`.
![ToolTimeoutCascadeBandAdvisor](../assets/demo/tool-timeout-cascade-band.gif)
### ToolTimeoutCascadeBandAdvisor

![ToolTimeoutCascadeBandAdvisor](../assets/demo/tool-timeout-cascade-band.gif)

Offline HITL `cascade_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen tool-timeout cascade monitors. See `docs/guides/TOOL_TIMEOUT_CASCADE_BAND_ADVISOR_GUIDE.md`.
![ActorMailboxOverflowAdvisor](../assets/demo/actor-mailbox-overflow.gif)
### ActorMailboxOverflowAdvisor

![ActorMailboxOverflowAdvisor](../assets/demo/actor-mailbox-overflow.gif)

Offline HITL `mailbox_depth_ratio` bands. Gap vs Ray/Akka/Orleans actor-mailbox overflow monitors. See `docs/guides/ACTOR_MAILBOX_OVERFLOW_ADVISOR_GUIDE.md`.
### MemoryNamespaceLeakAdvisor

![MemoryNamespaceLeakAdvisor](../assets/demo/memory-namespace-leak.gif)

Offline HITL `leak_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen memory-namespace leak monitors. See `docs/guides/MEMORY_NAMESPACE_LEAK_ADVISOR_GUIDE.md`.

### HandoffTimeoutBandAdvisor

![HandoffTimeoutBandAdvisor](../assets/demo/handoff-timeout-band.gif)

Offline HITL `timeout_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen handoff-timeout band monitors. See `docs/guides/HANDOFF_TIMEOUT_BAND_ADVISOR_GUIDE.md`.

### CriticDisagreementSpreadAdvisor

![CriticDisagreementSpreadAdvisor](../assets/demo/critic-disagreement-spread.gif)

Offline HITL `disagreement_ratio` bands. Gap vs AutoGen/CrewAI/LangGraph critic disagreement-spread monitors. See `docs/guides/CRITIC_DISAGREEMENT_SPREAD_ADVISOR_GUIDE.md`.

### ToolSideEffectLedgerAdvisor

![ToolSideEffectLedgerAdvisor](../assets/demo/tool-side-effect-ledger.gif)

Offline HITL `side_effect_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen tool side-effect ledger monitors. See `docs/guides/TOOL_SIDE_EFFECT_LEDGER_ADVISOR_GUIDE.md`.

### ToolResultSchemaLagAdvisor

![ToolResultSchemaLagAdvisor](../assets/demo/tool-result-schema-lag.gif)

Offline HITL advisor for `lag_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen tool-result schema lag monitors. Optional polish via GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.

### ParallelToolCollisionAdvisor

![ParallelToolCollisionAdvisor](../assets/demo/parallel-tool-collision.gif)

Offline HITL advisor for `collision_ratio` bands. Gap vs AutoGen/CrewAI/LangGraph parallel tool-collision monitors. Optional polish via GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.

### PlannerReplanThrashAdvisor

![PlannerReplanThrashAdvisor](../assets/demo/planner-replan-thrash.gif)

Offline HITL advisor for `replan_thrash_ratio` bands. Gap vs LangGraph/CrewAI/AutoGen planner replan-thrash monitors. Optional polish via GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.

### ToolPermissionEscalationBandAdvisor

![ToolPermissionEscalationBandAdvisor](../assets/demo/tool-permission-escalation-band.gif)

Offline HITL escalation_score bands. Gap vs AutoGen/CrewAI/LangGraph tool-permission escalation monitors. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/TOOL_PERMISSION_ESCALATION_BAND_ADVISOR_GUIDE.md`.

### CriticTimeoutCascadeGuard

![CriticTimeoutCascadeGuard](../assets/demo/critic-timeout-cascade.gif)

Offline HITL cascade_score bands. Gap vs AutoGen/CrewAI/LangGraph critic-timeout cascade guards. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/CRITIC_TIMEOUT_CASCADE_GUARD_GUIDE.md`.

### ConsensusVoteStuffingBandAdvisor

![ConsensusVoteStuffingBandAdvisor](../assets/demo/consensus-vote-stuffing.gif)

Offline HITL stuffing_score bands. Gap vs AutoGen/CrewAI/LangGraph consensus vote-stuffing band advisors. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/CONSENSUS_VOTE_STUFFING_ADVISOR_GUIDE.md`.

### AgentCapabilityRevocationBandAdvisor

![AgentCapabilityRevocationBandAdvisor](../assets/demo/agent-capability-revocation.gif)

Offline HITL revocation_score bands. Gap vs AutoGen/CrewAI/LangGraph agent-capability revocation band advisors. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/AGENT_CAPABILITY_REVOCATION_ADVISOR_GUIDE.md`.

### PlanGoalContradictionBandAdvisor

![PlanGoalContradictionBandAdvisor](../assets/demo/plan-goal-contradiction-band.gif)

Offline HITL contradiction_score bands. Gap vs AutoGen/CrewAI/LangGraph plan-goal contradiction band advisors. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/PLAN_GOAL_CONTRADICTION_BAND_ADVISOR_GUIDE.md`.

### ToolResultSizeBombGuard

![ToolResultSizeBombGuard](../assets/demo/tool-result-size-bomb.gif)

Offline HITL result_bytes bands. Gap vs AutoGen/CrewAI/LangGraph tool-result size-bomb guards. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/TOOL_RESULT_SIZE_BOMB_GUARD_GUIDE.md`.

### MessageBusPoisonPillGuard

![MessageBusPoisonPillGuard](../assets/demo/message-bus-poison-pill.gif)

Offline HITL poison_score bands. Gap vs AutoGen/CrewAI/LangGraph message-bus poison-pill guards. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/MESSAGE_BUS_POISON_PILL_GUARD_GUIDE.md`.

### OrphanTaskSweeperGuard

![OrphanTaskSweeperGuard](../assets/demo/orphan-task-sweeper-guard.gif)

Offline HITL orphan_count bands. Gap vs AutoGen/CrewAI/LangGraph orphan-task sweepers. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/ORPHAN_TASK_SWEEPER_GUARD_GUIDE.md`.

### ToolSandboxDnsRebindGuard

![ToolSandboxDnsRebindGuard](../assets/demo/tool-sandbox-dns-rebind-guard.gif)

Offline HITL rebind_score bands. Gap vs AutoGen/CrewAI/LangGraph tool-sandbox DNS-rebinding guards. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/TOOL_SANDBOX_DNS_REBIND_GUARD_GUIDE.md`.

### CriticCollusionBandAdvisor

![CriticCollusionBandAdvisor](../assets/demo/critic-collusion-band-advisor.gif)

Offline HITL collusion_score bands. Gap vs AutoGen/CrewAI/LangGraph critic-collusion band advisors. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/CRITIC_COLLUSION_BAND_ADVISOR_GUIDE.md`.

![OrchestratorRetryStormBandAdvisor](../assets/demo/orchestrator-retry-storm-band.gif)
### OrchestratorRetryStormBandAdvisor

![OrchestratorRetryStormBandAdvisor](../assets/demo/orchestrator-retry-storm-band.gif)

![ConsensusParticipationSkewAdvisor](../assets/demo/consensus-participation-skew.gif)
### ConsensusParticipationSkewAdvisor

![ConsensusParticipationSkewAdvisor](../assets/demo/consensus-participation-skew.gif)

### ToolSandboxEscapeAttemptBandAdvisor

![ToolSandboxEscapeAttemptBandAdvisor](../assets/demo/tool-sandbox-escape.gif)

Offline HITL `attempt_ratio` bands vs LangGraph/CrewAI/AutoGen tool sandbox-escape attempt monitors. Distinct from `ToolResultSchemaDriftBandAdvisor` / `ToolPermissionEscalationBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.

### ToolBudgetExhaustionBandAdvisor

![ToolBudgetExhaustionBandAdvisor](../assets/demo/tool-budget-exhaustion.gif)

Offline HITL `exhaustion_ratio` bands vs LangGraph/CrewAI/AutoGen tool budget-exhaustion monitors. Distinct from `ToolCallQuotaGuard` / `ToolRetryBudgetBandGuard`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.

### OrchestratorFanInStallBandAdvisor

![OrchestratorFanInStallBandAdvisor](../assets/demo/orchestrator-fan-in-stall.gif)

Offline HITL `stall_ratio` bands vs LangGraph/CrewAI/AutoGen orchestrator fan-in stall monitors. Distinct from `AgentHandoffLoopBandAdvisor` / `ConsensusQuorumStallAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.

### ToolIdempotencyCollisionBandAdvisor

![ToolIdempotencyCollisionBandAdvisor](../assets/demo/tool-idempotency-collision.gif)

Offline HITL `collision_ratio` bands vs LangGraph/CrewAI/AutoGen tool idempotency-collision monitors. Distinct from `ToolSideEffectReplayBandAdvisor` / `ToolResultSchemaDriftBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.

### MessageBusPartitionBandAdvisor

![MessageBusPartitionBandAdvisor](../assets/demo/message-bus-partition.gif)

Offline HITL `partition_ratio` bands vs LangGraph/CrewAI/AutoGen message-bus partition monitors. Distinct from `OrchestratorFanInStallBandAdvisor` / `SharedLockContentionBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.

### SharedMemoryQuotaThrashBandAdvisor

![SharedMemoryQuotaThrashBandAdvisor](../assets/demo/shared-memory-quota-thrash.gif)

Offline HITL `thrash_ratio` bands vs LangGraph/CrewAI/AutoGen shared-memory quota thrash monitors. Distinct from `SharedKvWriteAmplificationAdvisor` / `BlackboardReadStalenessAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2.

### CriticLatencySkewBandAdvisor

![CriticLatencySkewBandAdvisor](../assets/demo/critic-latency-skew.gif)

Gap vs LangGraph/CrewAI/AutoGen critic latency-skew monitors. Distinct from `CriticLatencySloBandGuard` / `CriticTimeoutBandGuard`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/CRITIC_LATENCY_SKEW_BAND_ADVISOR_GUIDE.md`.

### SubgraphDeadlockResidualBandAdvisor

![SubgraphDeadlockResidualBandAdvisor](../assets/demo/subgraph-deadlock-residual.gif)

Gap vs LangGraph/CrewAI/AutoGen subgraph deadlock-residual monitors. Distinct from `SubgraphCancelLeakAdvisor` / `AgentHandoffLoopBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/SUBGRAPH_DEADLOCK_RESIDUAL_BAND_ADVISOR_GUIDE.md`.

### PlannerContextOverflowBandAdvisor

![PlannerContextOverflowBandAdvisor](../assets/demo/planner-context-overflow.gif)

Gap vs LangGraph/CrewAI/AutoGen planner context-overflow monitors. Distinct from `PlannerStepBudgetBandAdvisor` / `PlannerHorizonBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/PLANNER_CONTEXT_OVERFLOW_BAND_ADVISOR_GUIDE.md`.

### WorkerQueueDepthBandAdvisor

![WorkerQueueDepthBandAdvisor](../assets/demo/worker-queue-depth.gif)

HITL `queue_depth_ratio` band guard. Gap vs LangGraph/CrewAI/AutoGen worker-queue depth monitors. Distinct from `WorkerStarvationBandAdvisor` / `WorkerHeartbeatMissBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/WORKER_QUEUE_DEPTH_BAND_ADVISOR_GUIDE.md`.

### HandoffSchemaDriftBandAdvisor

![HandoffSchemaDriftBandAdvisor](../assets/demo/handoff-schema-drift.gif)

HITL `drift_ratio` band guard. Gap vs LangGraph/CrewAI/AutoGen handoff-schema drift monitors. Distinct from `ToolResultSchemaDriftBandAdvisor` / `AgentHandoffLoopBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/HANDOFF_SCHEMA_DRIFT_BAND_ADVISOR_GUIDE.md`.

### AgentAffinitySkewBandAdvisor

![AgentAffinitySkewBandAdvisor](../assets/demo/agent-affinity-skew.gif)

HITL `skew_ratio` band guard. Gap vs LangGraph/CrewAI/AutoGen agent-affinity skew monitors. Distinct from `FanInSkewBandAdvisor` / `SharedStateWriteSkewBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/AGENT_AFFINITY_SKEW_BAND_ADVISOR_GUIDE.md`.

### CriticCalibrationDriftBandAdvisor

![CriticCalibrationDriftBandAdvisor](../assets/demo/critic-calibration-drift.gif)

HITL `drift_ratio` band guard. Gap vs LangGraph/CrewAI/AutoGen critic-calibration drift monitors. Distinct from `CriticCollusionBandAdvisor` / `CriticLatencySkewBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/CRITIC_CALIBRATION_DRIFT_BAND_ADVISOR_GUIDE.md`.

### PlannerGoalChurnBandAdvisor

![PlannerGoalChurnBandAdvisor](../assets/demo/planner-goal-churn.gif)

HITL `churn_ratio` band guard. Gap vs LangGraph/CrewAI/AutoGen planner goal-churn monitors. Distinct from `PlannerContextOverflowBandAdvisor` / `PlanGoalContradictionBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/PLANNER_GOAL_CHURN_BAND_ADVISOR_GUIDE.md`.

### SharedKvLeaseExpiryBandAdvisor

![SharedKvLeaseExpiryBandAdvisor](../assets/demo/shared-kv-lease-expiry.gif)

HITL `expiry_ratio` band guard. Gap vs LangGraph/CrewAI/AutoGen shared-KV lease-expiry monitors. Distinct from `BlackboardWriteLeaseAdvisor` / `SharedLockContentionBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/SHARED_KV_LEASE_EXPIRY_BAND_ADVISOR_GUIDE.md`.

### ToolSchemaCompatBandAdvisor

![ToolSchemaCompatBandAdvisor](../assets/demo/tool-schema-compat.gif)

HITL `compat_ratio` band guard. Gap vs LangGraph/CrewAI/AutoGen tool-schema compatibility monitors. Distinct from `ToolResultSchemaDriftBandAdvisor` / `ToolBudgetExhaustionBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/TOOL_SCHEMA_COMPAT_BAND_ADVISOR_GUIDE.md`.

### AgentTokenBudgetSkewBandAdvisor

![AgentTokenBudgetSkewBandAdvisor](../assets/demo/agent-token-budget-skew.gif)

HITL `skew_ratio` band guard. Gap vs LangGraph/CrewAI/AutoGen agent token-budget skew monitors. Distinct from `SessionTokenBudgetLedger` / `CriticTokenBudgetBandGuard`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/AGENT_TOKEN_BUDGET_SKEW_BAND_ADVISOR_GUIDE.md`.

### CriticScoreInflationBandAdvisor

![CriticScoreInflationBandAdvisor](../assets/demo/critic-score-inflation.gif)

HITL `inflation_ratio` band guard. Gap vs LangGraph/CrewAI/AutoGen critic score-inflation monitors. Distinct from `CriticCalibrationDriftBandAdvisor` / `CriticCollusionBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/CRITIC_SCORE_INFLATION_BAND_ADVISOR_GUIDE.md`.

### WorkerMailboxOverflowBandAdvisor

![WorkerMailboxOverflowBandAdvisor](../assets/demo/worker-mailbox-overflow.gif)

HITL `overflow_ratio` band guard. Gap vs LangGraph/CrewAI/AutoGen worker mailbox overflow monitors. Distinct from `WorkerQueueDepthBandAdvisor` / `WorkerStarvationBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/WORKER_MAILBOX_OVERFLOW_BAND_ADVISOR_GUIDE.md`.

### AgentAffinityDecayBandAdvisor

![AgentAffinityDecayBandAdvisor](../assets/demo/agent-affinity-decay.gif)

HITL `decay_ratio` band guard. Gap vs LangGraph/CrewAI/AutoGen agent affinity-decay monitors. Distinct from `AgentAffinitySkewBandAdvisor` / `StickyBotAffinityStore`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/AGENT_AFFINITY_DECAY_BAND_ADVISOR_GUIDE.md`.

### HitlTimeoutCascadeBandAdvisor

![HitlTimeoutCascadeBandAdvisor](../assets/demo/hitl-timeout-cascade.gif)

HITL `cascade_ratio` band guard. Gap vs LangGraph/CrewAI/AutoGen HITL timeout-cascade monitors. Distinct from `HandoffTimeoutBandAdvisor` / `ToolTimeoutCascadeBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/HITL_TIMEOUT_CASCADE_BAND_ADVISOR_GUIDE.md`.

### MemoryCompactionLagBandAdvisor

![MemoryCompactionLagBandAdvisor](../assets/demo/memory-compaction-lag.gif)

HITL `lag_ratio` band guard. Gap vs LangGraph/CrewAI/AutoGen memory-compaction lag monitors. Distinct from `SharedMemoryQuotaThrashBandAdvisor` / `SharedKvLeaseExpiryBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/MEMORY_COMPACTION_LAG_BAND_ADVISOR_GUIDE.md`.

### BlackboardWriteContentionBandAdvisor

![BlackboardWriteContentionBandAdvisor](../assets/demo/blackboard-write-contention.gif)

HITL `contention_ratio` band guard. Gap vs LangGraph/CrewAI/AutoGen blackboard write-contention monitors. Distinct from `SharedBlackboardWriteLease` / `SharedLockContentionBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/BLACKBOARD_WRITE_CONTENTION_BAND_ADVISOR_GUIDE.md`.

### ToolSideEffectOrphanBandAdvisor

![ToolSideEffectOrphanBandAdvisor](../assets/demo/tool-side-effect-orphan.gif)

HITL `orphan_ratio` band guard. Gap vs LangGraph/CrewAI/AutoGen tool side-effect orphan monitors. Distinct from `ToolSideEffectLedgerAdvisor` / `ToolSideEffectReplayBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/TOOL_SIDE_EFFECT_ORPHAN_BAND_ADVISOR_GUIDE.md`.


### SupervisorFanoutSkewBandAdvisor

![SupervisorFanoutSkewBandAdvisor](../assets/demo/supervisor-fanout-skew.gif)

HITL supervisor fanout skew_ratio band guard (never auto-acts). Gap vs LangGraph/CrewAI/AutoGen supervisor fanout-skew monitors. Distinct from `OrchestratorFanoutBudgetBandAdvisor` / `CriticFanoutSkewAdvisor`. Stack: GPT-6.1 / Claude Sonnet 5.5 / Gemini 3.x / Kimi K3. Guide: [`SUPERVISOR_FANOUT_SKEW_BAND_ADVISOR_GUIDE.md`](guides/SUPERVISOR_FANOUT_SKEW_BAND_ADVISOR_GUIDE.md).

### HitlApprovalStarvationBandAdvisor

![HitlApprovalStarvationBandAdvisor](../assets/demo/hitl-approval-starvation.gif)

HITL `starvation_ratio` band guard. Gap vs LangGraph/CrewAI/AutoGen HITL approval-starvation monitors. Distinct from `HitlTimeoutCascadeBandAdvisor` / `HitlApprovalGate`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/HITL_APPROVAL_STARVATION_BAND_ADVISOR_GUIDE.md`.

### SupervisorHandoffLoopBandAdvisor

![SupervisorHandoffLoopBandAdvisor](../assets/demo/supervisor-handoff-loop.gif)

HITL `loop_ratio` band guard. Gap vs LangGraph/CrewAI/AutoGen supervisor handoff-loop monitors. Distinct from `AgentHandoffLoopBandAdvisor` / `HandoffSchemaDriftBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/SUPERVISOR_HANDOFF_LOOP_BAND_ADVISOR_GUIDE.md`.

### SubgraphRetryAmplificationBandAdvisor

![SubgraphRetryAmplificationBandAdvisor](../assets/demo/subgraph-retry-amplification.gif)

HITL `amplification_ratio` band guard. Gap vs LangGraph/CrewAI/AutoGen subgraph retry-amplification monitors. Distinct from `ToolRetryBudgetBandGuard` / `ToolTimeoutCascadeBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/SUBGRAPH_RETRY_AMPLIFICATION_BAND_ADVISOR_GUIDE.md`.

### ToolResultTruncationBandAdvisor

![ToolResultTruncationBandAdvisor](../assets/demo/tool-result-truncation.gif)

Gap vs LangGraph/CrewAI/AutoGen tool-result truncation monitors. Distinct from `ToolResultSchemaDriftBandAdvisor` / `ToolBudgetExhaustionBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/TOOL_RESULT_TRUNCATION_BAND_ADVISOR_GUIDE.md`.

### SharedStateWriteSkewBandAdvisor

![SharedStateWriteSkewBandAdvisor](../assets/demo/shared-state-write-skew.gif)

Gap vs LangGraph/CrewAI/AutoGen shared-state write-skew monitors. Distinct from `SharedMemoryQuotaThrashBandAdvisor` / `SharedLockContentionBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/SHARED_STATE_WRITE_SKEW_BAND_ADVISOR_GUIDE.md`.

### AgentMemoryPoisonBandAdvisor

![AgentMemoryPoisonBandAdvisor](../assets/demo/agent-memory-poison.gif)

Gap vs LangGraph/CrewAI/AutoGen agent-memory poison monitors. Distinct from `SharedMemoryConflictBandAdvisor` / `PromptLeakBandAdvisor`. Stack: GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2. See `docs/guides/AGENT_MEMORY_POISON_BAND_ADVISOR_GUIDE.md`.

### OrchestratorPriorityInversionBandAdvisor

![OrchestratorPriorityInversionBandAdvisor](../assets/demo/orchestrator-priority-inversion.gif)

Offline HITL `inversion_ratio` bands vs LangGraph/CrewAI/AutoGen orchestrator priority-inversion monitors. Distinct from `OrchestratorFanInStallBandAdvisor` / `OrchestratorRetryStormBandAdvisor`.

### ConsensusVoteLatencySkewBandAdvisor

![ConsensusVoteLatencySkewBandAdvisor](../assets/demo/consensus-vote-latency-skew.gif)

Offline HITL `skew_ratio` bands vs LangGraph/CrewAI/AutoGen consensus vote latency-skew monitors. Distinct from `ConsensusQuorumStallAdvisor` / `ConsensusConfidenceBandAdvisor`.

### PlannerToolMismatchCascadeBandAdvisor

![PlannerToolMismatchCascadeBandAdvisor](../assets/demo/planner-tool-mismatch-cascade.gif)

Offline HITL `mismatch_ratio` bands vs LangGraph/CrewAI/AutoGen planner-tool mismatch cascade monitors. Distinct from `PlannerToolMismatchBandAdvisor` / `PlanGoalContradictionBandAdvisor`.

## Index and gap notes

- **ToolCallQuotaGuard**: Per-tool call quota per session advisory/hard deny — see `docs/guides/TOOL_CALL_QUOTA_GUARD_GUIDE.md`
- **HitlEscalationCooldownGate**: Cooldown after HITL deny/reject to block immediate re-escalation (advisory/hard; never network I/O) — see `docs/guides/HITL_ESCALATION_COOLDOWN_GATE_GUIDE.md`
- **BotRoleConflictDetector**: Exclusive role-tag collision detector (advisory/hard; never network I/O) — see `docs/guides/BOT_ROLE_CONFLICT_DETECTOR_GUIDE.md`
- **PlanStepDependencyResolver**: Topological plan-step ordering with cycle detection — see `docs/guides/PLAN_STEP_DEPENDENCY_RESOLVER_GUIDE.md`
- **BlackboardEntryTtlEvictor**: Per-key TTL eviction for shared blackboard entries — see `docs/guides/BLACKBOARD_ENTRY_TTL_EVICTOR_GUIDE.md`
- **BotHeartbeatLivenessWatchdog**: Per-bot heartbeat liveness (alive/stale/unknown) — see `docs/guides/BOT_HEARTBEAT_LIVENESS_WATCHDOG_GUIDE.md`
- **SharedBlackboardWriteLease**: Exclusive time-bounded blackboard write leases — see `docs/guides/SHARED_BLACKBOARD_WRITE_LEASE_GUIDE.md`
- **CriticPassBudgetLimiter**: Cap critic re-pass loops with HITL exhaust bands — see `docs/guides/CRITIC_PASS_BUDGET_LIMITER_GUIDE.md`
- **VoteTieBreakPolicy**: Deterministic multi-bot vote tie-break with HITL bands — see `docs/guides/VOTE_TIE_BREAK_POLICY_GUIDE.md`
- **BotSpawnBudgetLimiter**: Cap dynamic bot spawns per session with HITL bands — see `docs/guides/BOT_SPAWN_BUDGET_LIMITER_GUIDE.md`
- **AgentHandoffDepthLimiter**: Cap chained bot handoff depth with HITL bands — see `docs/guides/AGENT_HANDOFF_DEPTH_LIMITER_GUIDE.md`
- **ConsensusQuorumFloorGuard**: Require min yes-votes before consensus with HITL bands — see `docs/guides/CONSENSUS_QUORUM_FLOOR_GUARD_GUIDE.md`

- **ToolResultSchemaHashGate**: Flag tool-result schema hash drift with HITL bands — see `docs/guides/TOOL_RESULT_SCHEMA_HASH_GATE_GUIDE.md`
- **CriticTimeoutBandGuard**: Flag critic-pass waits vs timeout with HITL bands — see `docs/guides/CRITIC_TIMEOUT_BAND_GUARD_GUIDE.md`
- **ToolInvocationDeadlineGuard**: Flag per-tool invocation deadline pressure with HITL bands — see `docs/guides/TOOL_INVOCATION_DEADLINE_GUARD_GUIDE.md`
- **MultiBotLatencyBudgetAllocator**: Allocate per-bot latency shares vs a session budget with HITL bands — see `docs/guides/MULTI_BOT_LATENCY_BUDGET_ALLOCATOR_GUIDE.md`
- **ToolResultCardinalityGate**: Gate tool result row/item counts with HITL bands — see `docs/guides/TOOL_RESULT_CARDINALITY_GATE_GUIDE.md`
- **CriticPairwiseKappaGate**: Gate critic pairwise Cohen-kappa with HITL bands (ok/elevated/blocked) — see `docs/guides/CRITIC_PAIRWISE_KAPPA_GATE_GUIDE.md`
- **ToolSandboxCpuQuotaGuard**: Flag tool-sandbox CPU quota with HITL bands (ok/elevated/blocked) — see `docs/guides/TOOL_SANDBOX_CPU_QUOTA_GUARD_GUIDE.md`
- **CriticLatencySloBandGuard**: Flag critic-pass latency vs SLO with HITL bands (ok/elevated/blocked) — see `docs/guides/CRITIC_LATENCY_SLO_BAND_GUARD_GUIDE.md`
- **CriticSelfConsistencyBandGuard**: Flag critic disagreement-rate with HITL bands (ok/elevated/blocked) — see `docs/guides/CRITIC_SELF_CONSISTENCY_BAND_GUARD_GUIDE.md`
- **OrchestratorCascadeFailureAdvisor**: Advise orchestrator cascade-depth with HITL bands (ok/elevated/blocked) — see `docs/guides/ORCHESTRATOR_CASCADE_FAILURE_ADVISOR_GUIDE.md`
- **BlackboardStaleEntryAdvisor**: Flag/advise blackboard stale-entry age with HITL bands (ok/elevated/blocked) — see `docs/guides/BLACKBOARD_STALE_ENTRY_ADVISOR_GUIDE.md`
- **PlannerDepthCapAdvisor**: HITL bands (ok/elevated/blocked) — see `docs/guides/PLANNER_DEPTH_CAP_ADVISOR_GUIDE.md`
- **MessageBusBackpressureAdvisor**: Advise message-bus queue-depth backpressure with HITL bands (ok/elevated/blocked) — see `docs/guides/MESSAGE_BUS_BACKPRESSURE_ADVISOR_GUIDE.md`
- **BotCapabilityDriftAdvisor**: Advise bot capability drift_ratio with HITL bands (ok/elevated/blocked) — see `docs/guides/BOT_CAPABILITY_DRIFT_ADVISOR_GUIDE.md`
- **ConsensusQuorumBandGuard**: Flag consensus shortfall_ratio with HITL bands (ok/elevated/blocked) — see `docs/guides/CONSENSUS_QUORUM_BAND_GUARD_GUIDE.md`
- **PlanStepCycleDetectorGuard**: Flag plan-step cycle score with HITL bands (ok/elevated/blocked) — see `docs/guides/PLAN_STEP_CYCLE_DETECTOR_GUARD_GUIDE.md`
- **AgentHandoffLatencyAdvisor**: Advise agent-handoff latency with HITL bands (ok/elevated/blocked) — see `docs/guides/AGENT_HANDOFF_LATENCY_ADVISOR_GUIDE.md`
- **SharedMemoryPoisoningGuard**: Flag shared-memory poisoning score with HITL bands (ok/elevated/blocked) — see `docs/guides/SHARED_MEMORY_POISONING_GUARD_GUIDE.md`
- **ToolResultPoisoningGuard**: Flag tool-result poisoning score with HITL bands (ok/elevated/blocked) — see `docs/guides/TOOL_RESULT_POISONING_GUARD_GUIDE.md`
- **ToolRetryBudgetBandGuard**: Flag tool retry_count vs soft/hard budgets with HITL bands (ok/elevated/blocked) — see `docs/guides/TOOL_RETRY_BUDGET_BAND_GUARD_GUIDE.md`
- **CriticTokenBudgetBandGuard**: Flag critic token budget with HITL bands (ok/elevated/blocked) — see `docs/guides/CRITIC_TOKEN_BUDGET_BAND_GUARD_GUIDE.md`
- **ToolSandboxDiskQuotaGuard**: Flag tool-sandbox disk quota with HITL bands (ok/elevated/blocked) — see `docs/guides/TOOL_SANDBOX_DISK_QUOTA_GUARD_GUIDE.md`
- **OrchestratorFairnessAgingAdvisor**: Advise orchestrator wait-age fairness with HITL bands (ok/elevated/blocked) — see `docs/guides/ORCHESTRATOR_FAIRNESS_AGING_ADVISOR_GUIDE.md`
- **PlannerCostCeilingAdvisor**: Advise planner USD cost vs ceiling with HITL bands (ok/elevated/blocked) — see `docs/guides/PLANNER_COST_CEILING_ADVISOR_GUIDE.md`
- **ToolSandboxMemoryQuotaGuard**: Flag tool-sandbox memory quota with HITL bands (ok/elevated/blocked) — see `docs/guides/TOOL_SANDBOX_MEMORY_QUOTA_GUARD_GUIDE.md`
- **SharedMemoryTtlEvictionAdvisor**: Advise shared-memory TTL eviction with HITL bands (ok/elevated/blocked) — see `docs/guides/SHARED_MEMORY_TTL_EVICTION_ADVISOR_GUIDE.md`
- **PlannerBeamWidthLimiter**: Cap planner beam width with HITL bands (ok/elevated/blocked) — see `docs/guides/PLANNER_BEAM_WIDTH_LIMITER_GUIDE.md`
- **ToolSandboxEgressClassGuard**: Classify tool sandbox egress risk with HITL bands — see `docs/guides/TOOL_SANDBOX_EGRESS_CLASS_GUARD_GUIDE.md`
- **CriticAgreementEntropyGate**: Gate critic verdict agreement entropy with HITL bands — see `docs/guides/CRITIC_AGREEMENT_ENTROPY_GATE_GUIDE.md`
- **BlackboardWriteAmplificationBandGuard**: Flag blackboard write-amplification (writes/reads) with HITL bands — see `docs/guides/BLACKBOARD_WRITE_AMPLIFICATION_BAND_GUARD_GUIDE.md`
- **FanInSkewBandGuard**: Flag fan-in completion-time skew with HITL bands — see `docs/guides/FAN_IN_SKEW_BAND_GUARD_GUIDE.md`
- **PlannerGoalDriftGuard**: Flag planner goal drift with HITL bands — see `docs/guides/PLANNER_GOAL_DRIFT_GUARD_GUIDE.md`
- **ConsensusTimeoutBandGuard**: Flag consensus waits vs timeout with HITL bands — see `docs/guides/CONSENSUS_TIMEOUT_BAND_GUARD_GUIDE.md`
- **ToolResultPiiRedactionGate**: Gate tool-result PII with HITL bands — see `docs/guides/TOOL_RESULT_PII_REDACTION_GATE_GUIDE.md`
- **SharedMemoryConflictBandGuard**: Flag shared-memory version skew with HITL bands — see `docs/guides/SHARED_MEMORY_CONFLICT_BAND_GUARD_GUIDE.md`
- **PlannerReplanBudgetLimiter**: Cap planner replan attempts with HITL bands — see `docs/guides/PLANNER_REPLAN_BUDGET_LIMITER_GUIDE.md`
- **OrchestratorStallWatchdog**: Flag stalled orchestrator loops with HITL bands — see `docs/guides/ORCHESTRATOR_STALL_WATCHDOG_GUIDE.md`
- **CriticVerdictDiversityGate**: Flag echo-chamber critic verdicts with HITL bands — see `docs/guides/CRITIC_VERDICT_DIVERSITY_GATE_GUIDE.md`
- **ToolArgByteBudgetGuard**: Cap serialized tool-argument bytes with HITL bands — see `docs/guides/TOOL_ARG_BYTE_BUDGET_GUARD_GUIDE.md`
- **SharedMemoryQuotaGuard**: Per-bot shared-blackboard write quota with HITL bands — see `docs/guides/SHARED_MEMORY_QUOTA_GUARD_GUIDE.md`
- **DebateRoundLimiter**: Cap multi-bot debate rounds with HITL exhaust bands — see `docs/guides/DEBATE_ROUND_LIMITER_GUIDE.md`
- **ConsensusConfidenceBandAdvisor**: Map winning vote share into HITL confidence bands — see `docs/guides/CONSENSUS_CONFIDENCE_BAND_ADVISOR_GUIDE.md`
- **DeterministicRunSeedGuard**: Pin/validate deterministic run seeds for reproducible multi-bot runs — see `docs/guides/DETERMINISTIC_RUN_SEED_GUARD_GUIDE.md`
- **ToolCallWaveScheduler**: Dependency-depth parallel tool-call waves — see `docs/guides/TOOL_CALL_WAVE_SCHEDULER_GUIDE.md`
- **FanInBarrierGate**: Fan-in barrier releasing after N distinct bot arrivals — see `docs/guides/FAN_IN_BARRIER_GATE_GUIDE.md`
- **ToolResultFingerprintDeduper**: Fingerprint-hash tool-result dedupe per session to avoid re-injecting identical observations (never network I/O) — see `docs/guides/TOOL_RESULT_FINGERPRINT_DEDUPER_GUIDE.md`
- **BotSkillTagRouter**: Route tasks to bots by skill-tag overlap ranking — see `docs/guides/BOT_SKILL_TAG_ROUTER_GUIDE.md`
- **SessionTokenBudgetLedger**: Soft/hard cumulative token budget per session — see `docs/guides/SESSION_TOKEN_BUDGET_LEDGER_GUIDE.md`
- **BotVoteConsensusAggregator**: Majority/plurality vote across bot answers — see `docs/guides/BOT_VOTE_CONSENSUS_AGGREGATOR_GUIDE.md`
- **SessionTtlExpirer**: Per-session idle TTL with advisory/hard expiry — see `docs/guides/SESSION_TTL_EXPIRER_GUIDE.md`
- **ToolCallLatencyTracker**: Per-tool latency samples with advisory p50/p95 — see `docs/guides/TOOL_CALL_LATENCY_TRACKER_GUIDE.md`
- **CriticBotVerdictGate**: Critic accept/revise/reject verdict gate — see `docs/guides/CRITIC_BOT_VERDICT_GUIDE.md`
- **ConversationTurnBudgetGuard**: Max turns per session advisory/hard gate — see `docs/guides/CONVERSATION_TURN_BUDGET_GUIDE.md`
- **ToolPermissionAllowlist**: Per-bot tool ACL allow/deny gate — see `docs/guides/TOOL_PERMISSION_ALLOWLIST_GUIDE.md`
- **StickyBotAffinityStore**: session→bot sticky affinity for multi-bot continuity — see `docs/guides/STICKY_BOT_AFFINITY_GUIDE.md`
- **RunDeadlineWatchdog**: advisory wall-clock run deadline (remaining/expired) — see `docs/guides/RUN_DEADLINE_WATCHDOG_GUIDE.md`
- **ToolCallIdempotencyCache**: hash-keyed tool result replay for retries — see `docs/guides/TOOL_CALL_IDEMPOTENCY_CACHE_GUIDE.md`
- **ToolResultTruncator**: soft mid-string cap for oversized tool results before LLM context — see `docs/guides/TOOL_RESULT_TRUNCATOR_GUIDE.md`
- **SharedBlackboard**: typed cross-bot scratchpad with revision caps — see `docs/guides/SHARED_BLACKBOARD_GUIDE.md`
- **RateLimitedToolRunner**: per-tool sliding-window call budget — see `docs/guides/RATE_LIMITED_TOOL_RUNNER_GUIDE.md`
- **AdaptiveConcurrencyLimiter**: global in-flight tool cap with adaptive shrink — see `docs/guides/ADAPTIVE_CONCURRENCY_LIMITER_GUIDE.md`
- **ToolCircuitBreaker**: per-tool failure isolation (closed/open/half-open) — see `docs/guides/TOOL_CIRCUIT_BREAKER_GUIDE.md`
- **ObservationRedactor**: PII/token scrub before event logs — see `docs/guides/OBSERVATION_REDACTOR_GUIDE.md`
- **ToolArgumentSanitizer**: scrub secrets from tool args before execute — see `docs/guides/TOOL_ARGUMENT_SANITIZER_GUIDE.md`
- **ConversationSummarizer**: extractive rolling summary (head/tail + keywords) — see `docs/guides/CONVERSATION_SUMMARIZER_GUIDE.md`
- **ToolResultSchemaValidator**: validate ToolResult before observe — see `docs/guides/TOOL_RESULT_SCHEMA_VALIDATOR_GUIDE.md`
- **BudgetedStepPlanner**: token/cost-aware step caps before LLM calls — see `docs/guides/BUDGETED_STEP_PLANNER_GUIDE.md`
- **ToolRetryBackoffPolicy**: jittered exponential tool retries — see `docs/guides/TOOL_RETRY_BACKOFF_GUIDE.md`
- **EventLogCompactor**: bounded head/tail event-log compaction — see `docs/guides/EVENT_LOG_COMPACTOR_GUIDE.md`
- **RunReplayDiff**: run-to-run event-log drift diff (ignores timestamps) — see `docs/guides/RUN_REPLAY_DIFF_GUIDE.md`
- **SpeculativeToolPrefetch**: speculative next-tool ranking (never executes) — see `docs/guides/SPECULATIVE_TOOL_PREFETCH_GUIDE.md`

| Gap filled by `ConsensusConfidenceBandAdvisor` | Missing vote-share confidence bands after consensus | `ConsensusConfidenceBandAdvisor` — see `docs/guides/CONSENSUS_CONFIDENCE_BAND_ADVISOR_GUIDE.md` |
| Gap filled by `DeterministicRunSeedGuard` | Missing explicit run-seed reproducibility guard | `DeterministicRunSeedGuard` — see `docs/guides/DETERMINISTIC_RUN_SEED_GUARD_GUIDE.md` |
| Gap filled by `ToolCallQuotaGuard` | Missing per-session per-tool call quota | `ToolCallQuotaGuard` — see `docs/guides/TOOL_CALL_QUOTA_GUARD_GUIDE.md` |
| Gap filled by `BotTurnFairnessScheduler` | Missing turn fairness across bots | `BotTurnFairnessScheduler` — see `docs/guides/BOT_TURN_FAIRNESS_SCHEDULER_GUIDE.md` |
| Gap filled by `BotRoleConflictDetector` | Missing exclusive role-collision detection | `BotRoleConflictDetector` — see `docs/guides/BOT_ROLE_CONFLICT_DETECTOR_GUIDE.md` |
| Gap filled by `PlanStepDependencyResolver` | Missing explicit plan-step dependency resolver | `PlanStepDependencyResolver` — see `docs/guides/PLAN_STEP_DEPENDENCY_RESOLVER_GUIDE.md` |
| Gap filled by `BlackboardEntryTtlEvictor` | Missing per-entry blackboard TTL eviction | `BlackboardEntryTtlEvictor` — see `docs/guides/BLACKBOARD_ENTRY_TTL_EVICTOR_GUIDE.md` |
| Gap filled by `BotHeartbeatLivenessWatchdog` | Missing per-bot heartbeat liveness | `BotHeartbeatLivenessWatchdog` — see `docs/guides/BOT_HEARTBEAT_LIVENESS_WATCHDOG_GUIDE.md` |
| Gap filled by `SharedBlackboardWriteLease` | Missing exclusive blackboard write leases | `SharedBlackboardWriteLease` — see `docs/guides/SHARED_BLACKBOARD_WRITE_LEASE_GUIDE.md` |
| Gap filled by `ToolCallWaveScheduler` | Missing explicit dependency-depth tool waves | `ToolCallWaveScheduler` — see `docs/guides/TOOL_CALL_WAVE_SCHEDULER_GUIDE.md` |
| Gap filled by `FanInBarrierGate` | Missing explicit fan-in barrier gate | `FanInBarrierGate` — see `docs/guides/FAN_IN_BARRIER_GATE_GUIDE.md` |
| Gap filled by `ToolResultFingerprintDeduper` | Missing tool-result fingerprint dedupe | `ToolResultFingerprintDeduper` — see `docs/guides/TOOL_RESULT_FINGERPRINT_DEDUPER_GUIDE.md` |
| Gap filled by `HitlEscalationCooldownGate` | Missing HitlEscalationCooldownGate capability | `HitlEscalationCooldownGate` — see `docs/guides/HITL_ESCALATION_COOLDOWN_GATE_GUIDE.md` |
| Gap filled by `BotSkillTagRouter` | Missing skill-tag overlap bot router | `BotSkillTagRouter` — see `docs/guides/BOT_SKILL_TAG_ROUTER_GUIDE.md` |
| Gap filled by `SessionTokenBudgetLedger` | Missing per-session soft/hard cumulative token ledger | `SessionTokenBudgetLedger` — see `docs/guides/SESSION_TOKEN_BUDGET_LEDGER_GUIDE.md` |
| Gap filled by `BotVoteConsensusAggregator` | Missing majority/plurality bot consensus | `BotVoteConsensusAggregator` — see `docs/guides/BOT_VOTE_CONSENSUS_AGGREGATOR_GUIDE.md` |
| Gap filled by `SessionTtlExpirer` | Missing per-session idle TTL | `SessionTtlExpirer` — see `docs/guides/SESSION_TTL_EXPIRER_GUIDE.md` |
| Gap filled by `ToolCallLatencyTracker` | Missing local per-tool p50/p95 latency | `ToolCallLatencyTracker` — see `docs/guides/TOOL_CALL_LATENCY_TRACKER_GUIDE.md` |
| Gap filled by `CriticBotVerdictGate` | Missing critic accept/revise/reject gate | `CriticBotVerdictGate` — see `docs/guides/CRITIC_BOT_VERDICT_GUIDE.md` |
| Gap filled by `ConversationTurnBudgetGuard` | Missing per-session turn budget | `ConversationTurnBudgetGuard` — see `docs/guides/CONVERSATION_TURN_BUDGET_GUIDE.md` |
| Gap filled by `ToolPermissionAllowlist` | Missing per-bot tool ACL | `ToolPermissionAllowlist` — see `docs/guides/TOOL_PERMISSION_ALLOWLIST_GUIDE.md` |
| Gap filled by `StickyBotAffinityStore` | Missing sticky session→bot pin | `StickyBotAffinityStore` — see `docs/guides/STICKY_BOT_AFFINITY_GUIDE.md` |
| Gap filled by `RunDeadlineWatchdog` | Missing wall-clock advisory deadline | `RunDeadlineWatchdog` — see `docs/guides/RUN_DEADLINE_WATCHDOG_GUIDE.md` |
| Gap filled by `ToolCallIdempotencyCache` | Missing local tool idempotency | `ToolCallIdempotencyCache` — see `docs/guides/TOOL_CALL_IDEMPOTENCY_CACHE_GUIDE.md` |
| Gap vs popular stacks for `DeadLetterToolQueue` | Missing local HITL control | `DeadLetterToolQueue` adds offline HITL-safe behavior for GPT-5.5 / Claude Sonnet 4.6 / Gemini 3.x / Kimi K2 |
| Gap filled by `BotHandoffReceiptStore` | Missing structured bot handoff audit | `BotHandoffReceiptStore` — see `docs/guides/BOT_HANDOFF_RECEIPT_GUIDE.md` |
