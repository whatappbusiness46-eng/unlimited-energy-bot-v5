# Unlimited Energy Bot - deployment scope

This package contains the audited current application and deployment fixes.
Provider credentials are intentionally blank in `.env.example`.

Verified in code:
- Telegram polling + Flask health server
- MongoDB user/balance/activity/transaction layer
- Force join, ban, cooldown/duplicate protections
- Daily bonus, tasks, referral, wheel, lucky box, scratch, energy
- Premium/VIP and withdrawal administration
- CPAGrip offer feed + password-verified postback + idempotency
- Admin CPAGrip visibility and shortlink management

Important:
- CPAGrip must be configured with the exact offer feed URL and postback password from the provider.
- Automatic payment gateway integration is not included; withdrawals remain admin-reviewed unless an official payout API is configured.
- Live provider and end-to-end tests must be performed after deployment.
