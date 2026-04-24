# Architecture — runtime topology with trust boundaries

**Audience:** customer, not deep on Temporal concepts.
**Scope:** deployment-level view using Temporal Cloud. Three trust boundaries: customer's network, Temporal Cloud (control plane), and external SaaS systems. Emphasizes *where things run* and *what crosses boundaries*.

```mermaid
flowchart TB
    subgraph HUMANS[" "]
        direction LR
        PT[👤 Product team]
        SR[👤 Security reviewer]
        PE[👤 Platform engineer]
    end

    subgraph CUSTOMER["🏢 FinCo network — customer's AWS / VPC"]
        direction TB
        subgraph CLIENTS[" "]
            direction LR
            GL[GitLab runner<br/>front-door trigger]
            CLI[CLI: approve.py]
        end

        WORKERS[⚙️ Temporal Worker pool<br/><br/>runs LandingZoneWorkflow<br/>+ all activities<br/><br/>scales horizontally]

        TFSTATE[(Terraform state<br/>S3 backend)]
        TARGETS[🎯 Target AWS resources<br/>new accounts, VPCs, IAM, etc.]
    end

    subgraph CLOUD["☁️ Temporal Cloud — control plane"]
        direction LR
        SERVER[Temporal Server<br/>Frontend · History · Matching<br/>+ Temporal-managed persistence]
        UI[Temporal Cloud UI<br/>observability]
    end

    subgraph EXTERNAL["🌐 External SaaS APIs"]
        direction LR
        GH[GitHub API]
        JIRA[Jira API]
        DD[Datadog]
        SLACK[Slack]
    end

    PT --> GL
    SR --> CLI
    PE -. "observe" .-> UI
    PT -. "observe" .-> UI

    GL -. "start workflow" .-> SERVER
    CLI -. "Update: approval" .-> SERVER

    WORKERS <==> |"poll tasks · stream completions<br/>ONLY workflow history crosses this line<br/>mTLS or API-key auth"| SERVER

    WORKERS --> TARGETS
    WORKERS --> TFSTATE
    WORKERS --> GH
    WORKERS --> JIRA
    WORKERS --> DD
    WORKERS --> SLACK
```

## Key architectural points this diagram makes

1. **Workers live in the customer's network.** All code touching AWS, Terraform state, and external APIs runs inside FinCo's infrastructure. Temporal Cloud never reaches into the customer network.
2. **Only workflow history crosses to Temporal Cloud.** Activity inputs/outputs are part of that history (encrypted in transit), but there's no separate data-plane that sees business data.
3. **Workers scale horizontally.** Temporal Server assigns tasks; any available worker picks them up. Run 1 worker or 50.
4. **Temporal Cloud UI is the observability surface.** Platform engineers and product teams observe live workflows here — no custom dashboards required.
5. **GitLab runner and CLI are just Temporal *clients*.** They call the gRPC API to start workflows and send Updates. They're small pieces of glue.
