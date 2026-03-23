# flow

Scripted, deterministic contest-creation flow.

Replaces the open-ended agentic loop for contest creation with a two-phase
sequence that costs zero API tokens:

- **Research phase** — `CoverFetcher` fetches a random cover pair and downloads
  both images to temp files.  No LLM involved.
- **Browser phase** — a fixed step sequence drives `BrowserManager` directly.
  Each step checks its result dict; the first failure stops the run immediately.

All routes and CSS selectors come from a [`PlatformConfig`](platform.md),
so the flow itself contains no hardcoded values.

---

::: tot_agent.flow
    options:
      members:
        - ContestData
        - ContestCreationFlow
        - run_multi_user_flow
