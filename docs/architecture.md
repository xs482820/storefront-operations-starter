# Architecture

```text
Customer mini-program ─┐
                        ├─ FastAPI API ─ PostgreSQL
Employee mini-program ─┤       │
                        │       └─ Redis
Admin console ──────────┘
```

## Shared domain model

The API is the system of record. Product categories, products, SKUs, inventory, customers, orders, after-sales cases and operation records are shared by all three clients. Role-based endpoints keep the customer, employee and administrator workflows separate.

## Optional adapters

Payment, WeChat notifications, image generation and printing are configuration-driven integration points. They are disabled or mocked in the example configuration so a local instance does not contact external services. A production deployment should supply credentials through private environment variables or secret management, never through the repository.

## Deployment shape

`docker-compose.yml` starts PostgreSQL, Redis, the API and the administrative console for local use. The mini-programs are built separately with Taro and must be configured with a valid HTTPS API domain before production release.
