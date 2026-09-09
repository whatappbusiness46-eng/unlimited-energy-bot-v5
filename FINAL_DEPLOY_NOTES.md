# Final deployment notes

Providers configured for this build:
- CPAGrip offer feed + password-protected global postback
- Offerwall.me offers/tasks/shortlinks + verified postback


Required Render variables:
- BOT_TOKEN
- MONGO_URI
- ADMIN_ID
- PUBLIC_BASE_URL
- CPAGRIP_ENABLED=true
- CPAGRIP_API_KEY
- CPAGRIP_OFFERS_API_URL
- CPAGRIP_POSTBACK_PASSWORD
- REWARD_POINTS_PER_USD=1000
- CPAGRIP_USER_REWARD_PERCENT=40
- CPAGRIP_DEFAULT_USER_REWARD_POINTS=200
- OFFERWALLME_ENABLED=true
- OFFERWALLME_API_KEY
- OFFERWALLME_BEARER_TOKEN
- OFFERWALLME_POSTBACK_SECRET
- OFFERWALLME_USER_REWARD_PERCENT=40
- OFFERWALLME_REWARD_UNIT=points
- OFFERWALLME_POINTS_PER_USD=1000
- OFFERWALLME_CURRENCY_PER_USD=200

CPAGrip postback URL:
`https://unlimited-energy-bot-v5.onrender.com/cpagrip/postback`

Do not commit or paste secrets into source control or chat.


### Task verification
Task verification is OFF by default. Set Render environment variable `TASK_VERIFICATION_ENABLED=true` to enable configured verification checks; leave it `false` to allow admin-controlled task completion without automatic verification.
