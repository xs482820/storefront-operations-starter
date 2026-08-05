# Storefront Operations Starter

[English](README.md) | [简体中文](README.zh-CN.md)

An open-source storefront operations system for small retail and wholesale businesses.

It brings customer ordering, staff fulfillment, and store administration into one codebase. Use it as a self-hosted starting point for a private shop, a local retailer, or a lightweight wholesale operation.

> This repository is a generic starter. It contains no production database, customer records, store identity, payment credentials, Mini Program AppIDs, AI keys, printer credentials, or uploaded files.

## Why This Project

Small stores often need more than a storefront but less than a large ERP. This project focuses on the everyday operational loop:

- Publish products with categories, SKUs, inventory, and retail/wholesale prices.
- Let customers browse, order, manage addresses, request after-sales service, and receive notices.
- Give staff a focused workspace for order fulfillment, shipping evidence, and read-only customer/product lookup.
- Give store owners a web admin for products, orders, after-sales cases, accounts, store settings, and audit logs.

Optional integration points are included for printing and AI image tasks. They are disabled by default and do not lock you into a vendor.

## Project Status

This project is maintained by an individual developer and grew out of hands-on exploration in a real operating context. It has known gaps in documentation, test coverage, deployment ergonomics, and edge-case handling. Feedback and focused contributions are welcome.

The production deployment remains the primary maintenance priority, so this public starter does not promise a fixed release schedule or feature parity with any private deployment. Updates are published when they can be generalized safely and are useful to other self-hosted users.

## Architecture

```text
Customer Mini Program  ─┐
Staff Mini Program     ─┼── FastAPI API ── PostgreSQL / Redis
Admin Web Console      ─┘
```

| Part | Stack | Purpose |
| --- | --- | --- |
| `backend/` | FastAPI, SQLAlchemy, Alembic | API, authorization, business rules, jobs |
| `frontend-admin/` | Vue 3, TypeScript, Vite, Element Plus | Store administration console |
| `baby-mall-fresh-taro/` | Taro 4, React, TypeScript | Customer-facing Mini Program |
| `baby-mall-employee-taro/` | Taro 4, React, TypeScript | Staff workbench Mini Program |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 20+ for Mini Program development
- WeChat Developer Tools if you want to compile the Taro apps as Mini Programs

### Run the backend and admin console

1. Copy `.env.example` to `.env` and replace `JWT_SECRET_KEY` with a long random value.
2. Copy `backend/data/storefront-config.example.json` to `backend/data/storefront-config.json`.
3. Start the local stack:

   ```bash
   docker compose up --build
   ```

4. Open `http://localhost:19080` for the admin console. The API is available at `http://localhost:19000`.

Run database migrations according to your deployment workflow, then create your own administrator, staff accounts, categories, and products. No default administrator password is included.

### Run a Mini Program

Each Taro project has its own `package.json`:

```bash
cd baby-mall-fresh-taro
npm install
npm run dev:weapp
```

Import the project into WeChat Developer Tools, set your own AppID in `project.config.json`, and configure an HTTPS API domain for production. Repeat the same process in `baby-mall-employee-taro` for the staff app.

## Integrations

The core system runs without any third-party commercial integration. Enable these only when you have configured your own credentials:

- **WeChat capabilities**: payment, phone-number access, and subscription messages.
- **AI images**: an OpenAI-compatible image service, with keys stored only in your private deployment environment.
- **Printing**: a printer gateway that consumes print jobs created by the backend.

## Deployment Notes

- Use HTTPS and a strong `JWT_SECRET_KEY` in production.
- Keep `.env`, certificates, uploads, database backups, and real `storefront-config.json` files outside Git.
- Review payment, delivery, and after-sales rules before serving real customers. The included flows are a foundation, not legal or accounting advice.

## Contributing

Contributions are welcome. Small, focused pull requests are easiest to review:

1. Open an issue describing the problem or proposed change.
2. Keep changes scoped and include a reproducible check for non-trivial logic.
3. Do not include credentials, production data, customer information, or vendor-specific private configuration.

## Roadmap

- Improve local development fixtures and demo data.
- Add deployment guides for common self-hosted environments.
- Expand printer gateway examples and integration documentation.
- Improve accessibility and cross-device Mini Program testing.

## License

Released under the [MIT License](LICENSE).
