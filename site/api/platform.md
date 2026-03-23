# platform

Platform configuration for the scripted contest-creation flow.

A `PlatformConfig` is a plain data class that declares the routes and CSS
selectors for a specific web application's login and contest-creation UI.
Swapping platforms requires only a new `PlatformConfig` instance — no changes
to flow logic, browser code, or cover fetching.

See [Adding a Platform](../adding-a-platform.md) for a step-by-step authoring
guide including a worked example, selector-finding tips, and a pre-ship
checklist.

---

::: tot_agent.platform
    options:
      members:
        - PlatformConfig
        - THIS_OR_THAT
