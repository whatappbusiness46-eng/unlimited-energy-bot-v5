# Final deployment notes

Providers configured from the supplied official documentation:
- CPAGrip offer feed + password-protected global postback
- ShrtFly Developer API (`https://shrtfly.com/api`)
- ShrinkMe Developers API (`https://shrinkme.io/api`)

Important: ShrtFly and ShrinkMe documentation supplied for this build only documents link creation. It does not document a server-to-server completion callback. Therefore the bot does **not** award points merely because a ShrtFly/ShrinkMe short link was created or clicked.

Required Render variables:
- BOT_TOKEN
- MONGO_URI
- ADMIN_ID
- PUBLIC_BASE_URL
- CPAGRIP_ENABLED=true
- CPAGRIP_API_KEY
- CPAGRIP_OFFERS_API_URL
- CPAGRIP_POSTBACK_PASSWORD
- REWARD_POINTS_PER_USD
- SHRTFLY_ENABLED=true
- SHRTFLY_API_TOKEN
- SHRTFLY_API_URL=https://shrtfly.com/api
- SHRINKME_ENABLED=true
- SHRINKME_API_KEY
- SHRINKME_API_URL=https://shrinkme.io/api

CPAGrip postback URL:
`https://unlimited-energy-bot-v2-06pl.onrender.com/cpagrip/postback`

Do not commit or paste secrets into source control or chat.
