# Accounts, saved projects, and Lifetime checkout

The Account screen supports registration, sign-in, profile names, password changes, and sign-out. My projects lists only the signed-in user's projects, including drafts. Project records, generation history, and files persist in `PPM_DATA_DIR`; back up the entire directory, including `studio.sqlite3`. SQLite sessions persist across restarts. Password changes revoke other sessions.

The Quality checks navigation and panel have been removed. Internal generation validation remains enabled.

## Configuration

Export the variables in `.env.example` before starting the server; the application does not automatically load this file. Set `PPM_PUBLIC_URL` to the real HTTPS origin in deployment. Use the same origin for frontend and API. Set `PPM_FREE_PROJECT_LIMIT` to the desired Starter allowance (provisional default: 3). Lifetime removes the project-count limit; it does not promise unlimited disk space. Apply deployment storage quotas and backups as appropriate.

No payment credentials or sale price are included. Purchases remain disabled until all three Stripe settings are configured. The Stripe integration is optional and has only been verified with mocked provider responses and signed test events, not a live transaction.

1. In Stripe, create an active **one-time** price in your chosen currency.
2. Set `STRIPE_SECRET_KEY`, `STRIPE_LIFETIME_PRICE_ID`, and `STRIPE_WEBHOOK_SECRET` securely on the server. Start with test-mode credentials; never put secrets in frontend files or commit them.
3. Configure the webhook URL `https://YOUR_HOST/api/billing/webhook` for `checkout.session.completed`, `checkout.session.async_payment_succeeded`, and `checkout.session.expired`.
4. Validate a complete test-mode checkout and webhook delivery before switching to live credentials and a live price. The UI marks test checkout explicitly.

Access is granted only after a signed, fresh webhook matches the recorded Checkout session, account, amount, currency, purchase metadata, and test/live mode. A success redirect cannot grant access. Repeated webhook deliveries are idempotent. Pending Checkout sessions are reused. No card data is stored in this app. Refunds, disputes, tax configuration, account email verification, and forgotten-password recovery are not automated in this version; these need completion before a public commercial launch. Authentication rate limiting is per process; use a shared limiter for multi-worker deployment.

Implementation references: [Stripe Checkout session creation](https://docs.stripe.com/api/checkout/sessions/create), [fulfillment](https://docs.stripe.com/checkout/fulfillment), [webhook endpoints](https://docs.stripe.com/events/manage-webhook-endpoints).

## Existing local projects

Pre-account projects remain in the database and on disk with no owner. They are not exposed to a newly registered account automatically. After registering the intended owner, an operator can preview a deliberate migration:

```sh
.venv/bin/python scripts/assign_local_projects.py --data-dir .data --email owner@example.com
```

Review the list, back up the data directory, then run the same command with `--apply`. This assigns only unowned projects; it does not change projects already owned by other accounts. No migration has been applied to the existing local projects by this change.
