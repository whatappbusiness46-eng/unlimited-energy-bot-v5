# Offerwall.me-only task enhancement

This build focuses the user-facing task flow on Offerwall.me.

## Included
- Offerwall.me tasks are grouped into Easy Tasks, App Install, Video Ads, Surveys and Other Tasks.
- Categories are inferred from provider metadata plus task title/description/instructions; no fake provider offers are created.
- Task details now show the detected task type and platform when available.
- Existing Offerwall.me verified postback/reward flow remains in place.
- CPAlead Bangladesh Tasks UI was removed from the user-facing callback flow.

## Important
Video Ads appear only when Offerwall.me's current task inventory returns a video/rewarded-ad type offer. The bot does not invent a video-ad URL or reward.

Keep these Render ENV values configured:
- OFFERWALLME_ENABLED=true
- OFFERWALLME_API_KEY
- OFFERWALLME_BEARER_TOKEN
- OFFERWALLME_POSTBACK_SECRET
- OFFERWALLME_USER_REWARD_PERCENT=40
- OFFERWALLME_REWARD_UNIT=points
- OFFERWALLME_POINTS_PER_USD=1000
- OFFERWALLME_CURRENCY_PER_USD=200
- OFFERWALLME_COUNTRY=BD
- OFFERWALLME_TASK_LIMIT=20

Offerwall.me's public homepage currently states that it has paid $24.5K to publishers. This is the provider's own published figure, not an independent guarantee. Verified S2S postback should remain enabled before member rewards are credited.
