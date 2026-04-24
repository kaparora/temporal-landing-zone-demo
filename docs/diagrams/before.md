# Before — the current state

**Audience:** customer, not deep on Temporal concepts.
**Scope:** FinCo's regulated-team onboarding as it exists today — a patchwork of pipelines, external state stores, cron pollers, Slack-driven approvals, and platform-engineer firefighting. The visual density *is* the pain.

```mermaid
flowchart TB
    subgraph PT["1 · Product Team"]
        direction LR
        PT1[File Jira ticket]
        PT2[Poll status. Again.]
    end

    subgraph PIPES["2 · GitLab Pipelines — 3 chained"]
        direction LR
        P1[#1: AWS + networking]
        P2[#2: IAM + SSO]
        P3[#3: GitHub, Jira, Datadog]
    end

    subgraph PLUMB["3 · Pipeline plumbing — hacks"]
        direction LR
        S3[S3<br/>TF state hand-off]
        DDB[DynamoDB<br/>step tracker]
        CRON[Cron job<br/>poll AWS every 5 min]
    end

    subgraph SEC["4 · Slack approval flow — separate"]
        direction LR
        SB[Slack bot]
        AP[Approval pipeline]
    end

    subgraph SR["5 · Security Reviewer"]
        direction LR
        SR1[Acks in Slack<br/>days later]
    end

    subgraph PE["6 · Platform Engineer — firefighting"]
        direction LR
        RB[40-page runbook]
        FF[Manual recovery]
    end

    subgraph AWS["7 · AWS"]
        direction LR
        A1[AWS account]
        A2[VPC + subnet + IGW]
        ORPH[🧟 Orphaned resources<br/>from failed runs]
    end

    subgraph EXT["8 · External Systems"]
        direction LR
        E1[GitHub repo]
        E2[Jira project]
        E3[Datadog + CloudWatch]
    end

    PT1 --> P1
    P1 -.-> S3
    P1 --> A1
    CRON -. "polls" .-> A1
    P1 -. "blocks until<br/>cron confirms" .-> P2
    P1 -. "requests approval" .-> SB
    SB --> AP
    AP -. "notifies" .-> SR1
    SR1 -. "approve" .-> AP
    AP -. "unblock" .-> P2
    P2 -.-> S3
    P2 -.-> DDB
    P2 --> A2
    P3 -.-> DDB
    P3 --> E1
    P3 --> E2
    P3 --> E3
    P1 -. "fails ~20%" .-> RB
    P2 -. "fails" .-> RB
    P3 -. "fails" .-> RB
    RB --> FF
    FF -. "misses cleanup" .-> ORPH
    PT2 -. "is it done?" .-> DDB
```
