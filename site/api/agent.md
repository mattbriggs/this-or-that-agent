# tot_agent.agent

Core agentic loop, Observer pattern implementation, and Goal template builders.

## Observer pattern classes

```mermaid
classDiagram
    class AgentObserver {
        <<abstract>>
        +on_event(event: AgentEvent) None
    }
    class ConsoleObserver {
        -_console: Console
        +on_event(event: AgentEvent) None
    }
    class LoggingObserver {
        -_log: Logger
        +on_event(event: AgentEvent) None
    }
    AgentObserver <|-- ConsoleObserver
    AgentObserver <|-- LoggingObserver
    BrowserAgent --> AgentObserver : notifies
    BrowserAgent --> AgentEvent : emits
```

## Goal template hierarchy

```mermaid
classDiagram
    class GoalTemplate {
        <<abstract>>
        +build(**kwargs) str
    }
    class CreateTestsGoal {
        +count: int
        +genre: str
        +build() str
    }
    class VoteGoal {
        +username: str
        +password: str
        +vote_count: int
        +bias: str
        +build() str
    }
    class SimulateAllUsersGoal {
        +vote_count_each: int
        +build() str
    }
    class FullSeedGoal {
        +test_count: int
        +vote_rounds: int
        +build() str
    }
    GoalTemplate <|-- CreateTestsGoal
    GoalTemplate <|-- VoteGoal
    GoalTemplate <|-- SimulateAllUsersGoal
    GoalTemplate <|-- FullSeedGoal
```

## Module reference

::: tot_agent.agent
    options:
      members:
        - EventType
        - AgentEvent
        - AgentObserver
        - ConsoleObserver
        - LoggingObserver
        - BrowserAgent
        - GoalTemplate
        - CreateTestsGoal
        - VoteGoal
        - SimulateAllUsersGoal
        - FullSeedGoal
