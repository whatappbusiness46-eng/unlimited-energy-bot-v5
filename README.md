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