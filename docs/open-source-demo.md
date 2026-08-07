# Open-source demo environment

This stack is separate from the default development environment. It starts with one local administrator, three neutral sample products, and a single notice. It never imports customers, orders, payments, after-sales records, uploads, or production configuration.

1. Copy `.env.oss-demo.example` to `.env.oss-demo`.
2. Replace `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`, `DATABASE_URL`, and `DEMO_ADMIN_PASSWORD` with local secrets.
3. Start the demo:

```bash
docker compose --env-file .env.oss-demo --project-name storefront-oss-demo -f docker-compose.yml -f docker-compose.oss-demo.yml up --build -d
```

Open the admin console at `http://localhost:19180`. The API is available at `http://localhost:19100`.

To reset only the demo data and volumes:

```bash
docker compose --env-file .env.oss-demo --project-name storefront-oss-demo -f docker-compose.yml -f docker-compose.oss-demo.yml down -v
```

The public customer and employee clients should point to the demo API only when testing this environment. Store identity, contact details, banners, notices, shipping rules, watermark, and print layout are read from the backend and maintained in the admin console. Fixed interface controls remain in the client code.
