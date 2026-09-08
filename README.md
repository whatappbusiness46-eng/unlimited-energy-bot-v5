# Unlimited Energy Bot — Final Ready

Existing bot with the Phase 1–19 application features retained.

## Monetization scope
- CPAGrip live offers with verified server-to-server postback.
- ShrtFly and ShrinkMe shortlinks can be managed from the Admin panel.
- Manual client-side offer claiming is disabled.

## Admin
The Admin panel supports:
- Add/enable/disable/delete shortlinks.
- View cached CPAGrip offers.
- Hide/show CPAGrip offers.
- Delete cached CPAGrip offers.
- VIP Purchase ON/OFF.
- Existing user/reward/withdrawal administration.

## Important
Provider APIs and postback signatures are deliberately configurable. The bot does not invent undocumented endpoints or signatures. Copy the exact endpoint, parameter names and signature formula from the provider documentation into Render environment variables.

Shortlink completion must only be rewarded if the shortlink provider's documented completion mechanism is used. A simple Telegram "Verify" button is not proof of an ad-view/conversion.

## Render
Set the variables from `.env.example`. Never commit real tokens or API keys.

## Health
- `/health`
- `/health/providers`

## Postback
- `/postback/cpagrip`

Use HTTPS and the exact provider postback URL shown in your provider dashboard.
\n\n### Deployment hotfix\n- Premium/VIP admin toggle persistence is resilient to callback acknowledgement.\n- Task index initialization safely handles an existing differently named `id` index.\n

### Task verification
Task verification is OFF by default. Set Render environment variable `TASK_VERIFICATION_ENABLED=true` to enable configured verification checks; leave it `false` to allow admin-controlled task completion without automatic verification.


## Offerwall.me
- Ownership verification meta tag is served from `/`.
- S2S postback endpoint: `/postback/offerwallme`.
- Render environment variables: `OFFERWALLME_ENABLED=true`, `OFFERWALLME_POSTBACK_SECRET`, `OFFERWALLME_USER_REWARD_PERCENT` (default 40), `OFFERWALLME_POINTS_PER_USD` (default 1000).
- Configure the Offerwall.me placement domain as the Render hostname only (no `https://` and no path), and use the full `/postback/offerwallme` URL for the postback.
- The bot accepts numeric Telegram user IDs as Sub ID, validates the server-side secret/signature, converts approved USD payout to member points, prevents duplicate event crediting, and records reversals without inventing a reward.
- The exact signature field/algorithm must match the parameters Offerwall.me sends for the publisher account. The endpoint fails closed when authentication is missing or invalid.
