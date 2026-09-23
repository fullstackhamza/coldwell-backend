# Coldwell API

FastAPI + MongoDB backend for the Coldwell frontend. This is a separate
service from the Next.js app — run them side by side, same as the
Courtside Arena project (frontend on :3000, this on :8000).

## Setup

### 1. Get a MongoDB Atlas connection string

If you don't already have a cluster from a previous project:

1. Go to [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas) and
   sign in (or create a free account).
2. Create a free (M0) cluster if you don't have one.
3. Under **Database Access**, make sure you have a database user with a
   username/password.
4. Under **Network Access**, add your IP address (or `0.0.0.0/0` for "allow
   from anywhere" while developing — tighten this before going live).
5. Click **Connect** on your cluster > **Drivers** > copy the connection
   string. It looks like:
   `mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net`

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and paste your real connection string into `MONGODB_URI`
(with your actual username and password substituted in).

### 3. Install dependencies

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 4. Seed the database

This loads the same 13 demo products the frontend currently uses locally,
so the two match once the frontend is wired up to this API:

```bash
python -m app.seed
```

Safe to re-run — it skips any product that already exists.

### 5. Run the server

```bash
uvicorn app.main:app --reload --port 8000
```

Visit **http://localhost:8000/docs** for interactive API documentation
(Swagger UI) — you can try every endpoint from the browser, including
authenticated ones (click "Authorize" and paste in a token from
`/api/auth/login`).

## Running tests

Tests use `mongomock` (an in-memory fake MongoDB), so they don't touch your
real Atlas database:

```bash
pip install -r requirements-dev.txt
pytest -v
```

## API reference

All responses are JSON with **camelCase** keys (matching the frontend's
existing TypeScript types exactly). Query parameters are snake_case.

### Products
- `GET /api/products` — list, with optional query params: `category`,
  `subcategory` (repeatable), `colors` (repeatable), `sizes` (repeatable),
  `price_min`, `price_max`, `collection` (`new-arrivals` / `best-sellers`,
  repeatable), `on_sale`, `in_stock`, `sort`
  (`recommended`/`newest`/`price-asc`/`price-desc`/`best-selling`), `q`
  (free-text search over name/description/subcategory), `page` + `limit`
  (both optional — omit both to get the full list, unchanged from before).
  The response always includes an `X-Total-Count` header with the total
  match count before pagination is applied.
- `GET /api/products/{slug}` — single product, 404 if not found
- `POST /api/products` — create (requires a Bearer token)
- `PUT /api/products/{slug}` — partial update. **Requires an admin account**
  (see "Creating an admin" below) — a valid token from a plain customer
  gets a 403, not just any logged-in user.
- `DELETE /api/products/{slug}` — delete. Same admin requirement.

### Uploads
- `POST /api/uploads` — **admin only.** Multipart form with a `file` field
  (JPEG/PNG/WEBP/GIF, max `MAX_UPLOAD_MB`, default 5MB). Returns
  `{ "url": "http://.../uploads/<generated-name>.jpg" }`. Save that URL
  into a product's `images` array via `PUT /api/products/{slug}`.

### Auth
- `POST /api/auth/signup` — `{ fullName, email, password }` → returns a
  token + user. New accounts are always `role: "customer"` — there's no
  way to self-assign admin through the API.
- `POST /api/auth/login` — `{ email, password }` → returns a token + user
- `GET /api/auth/me` — requires a Bearer token, returns the current user
  (including their `role`)

### Orders
- `POST /api/orders` — `{ items, address, paymentMethod }`. Works with or
  without a Bearer token (guest checkout is allowed, same as the frontend).
  Prices are always looked up from the database — never trusted from the
  request.
- `GET /api/orders/{orderNumber}` — public lookup, used by the order
  confirmation page. Accepts an optional `?phone=` query param — when
  provided, it must match the order's phone number or the response is a
  404 (same as a genuinely unknown order number, so this can't be used to
  find out whether an order number exists). Used by the guest
  order-tracking page, which requires both the order number and phone.
- `GET /api/orders/mine` — requires a Bearer token, returns only that
  user's orders
- `GET /api/orders` — **admin only.** Every order in the store, newest
  first — powers the admin orders dashboard.
- `PATCH /api/orders/{orderNumber}/status` — **admin only.**
  `{ status }`, one of `Pending` / `Confirmed` / `Processing` / `Shipped`
  / `Delivered` / `Cancelled`. Anything else is a 400; an unknown order
  number is a 404.

## Creating an admin

There's no signup flag or API call for this — on purpose, so it can't be
done by accident or by an attacker. Instead:

1. Sign up normally through the site (or via `POST /api/auth/signup`) with
   the account you want to be the admin.
2. Run:

   ```bash
   python -m app.create_admin someone@example.com
   ```

   This flips that account's `role` to `"admin"` directly in the database.
3. Log out and back in on the frontend (or just refresh — the admin check
   is done live against the database on every request, not baked into the
   token, so it takes effect immediately either way).

## Product images

**In local development** (no Cloudinary env vars set): images save to disk
under `UPLOAD_DIR` (default `./uploads/`) and are served at
`/uploads/<filename>`. Zero setup needed.

**In production**: set `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, and
`CLOUDINARY_API_SECRET` (free account, see the deployment guide) and
`app/storage.py` automatically switches to Cloudinary — no code changes
needed. This matters because most free/cheap hosts (Render, Railway, Fly,
Heroku, etc.) wipe local disk on every redeploy or restart, which would
silently delete every uploaded product photo.

## Known limitations (by design, for now)

- **No real payment gateway.** "Online Payment" and "Bank Transfer" are
  currently just labels stored on the order — no Stripe/JazzCash/EasyPaisa
  integration exists yet. Wire one up in `routers/orders.py` before
  accepting real money.
- **Rate limiting is in-memory** (`app/rate_limit.py`) — fine for a single
  process, but won't share state across multiple workers/instances. Swap
  for Redis-backed limits before running more than one uvicorn worker.
- **Search is a regex scan**, not a proper text index — fine for a demo
  catalog, worth moving to a Mongo `$text` index or a dedicated search
  service once the catalog is large.
