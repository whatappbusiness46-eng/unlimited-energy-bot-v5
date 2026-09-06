# Provider setup checklist

## CPAGrip
Required:
- CPAGRIP_API_KEY
- CPAGRIP_OFFERS_API_URL
- CPAGRIP_POSTBACK_SECRET
- CPAGRIP_POSTBACK_SIGNATURE_TEMPLATE (only if CPAGrip documents an HMAC signature)

The API URL and signature template must be copied from CPAGrip's current documentation. Do not guess.

## ShrtFly / ShrinkMe
Required credentials:
- SHRTFLY_API_TOKEN / SHRTFLY_API_URL
- SHRINKME_API_KEY / SHRINKME_API_URL

The exact request/response parameters must be copied from each provider's current developer documentation. The bot does not fabricate an API contract.

## Security
Never send BOT_TOKEN, MONGO_URI, API keys or postback secrets in chat. Store them in Render Environment Variables.
