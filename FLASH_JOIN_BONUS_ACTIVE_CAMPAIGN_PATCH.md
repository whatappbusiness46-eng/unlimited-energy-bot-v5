# Flash Join Bonus + Active Campaign Patch

Added without removing existing earning/withdrawal/referral/provider systems.

## New behavior
- Automatic 24-hour join cash bonus, credited through the existing Points balance.
- Default conversion: 10 Points = ৳1.
- Tiers: first 100 = ৳50, next 250 = ৳20, next 500 = ৳5.
- One join bonus claim per Telegram user.
- Automatic congratulations notification after successful credit.
- Active campaign score tracks completed tasks and qualified referrals.
- Added Active Leaderboard button/page; no fixed VIP recipient count is shown.
- Campaign score fields are stored on user documents.

## Render ENV overrides
JOIN_BONUS_ENABLED=true
JOIN_BONUS_POINTS_PER_BDT=10
JOIN_BONUS_DURATION_SECONDS=86400
JOIN_BONUS_FIRST_TIER_COUNT=100
JOIN_BONUS_FIRST_TIER_BDT=50
JOIN_BONUS_SECOND_TIER_COUNT=250
JOIN_BONUS_SECOND_TIER_BDT=20
JOIN_BONUS_THIRD_TIER_COUNT=500
JOIN_BONUS_THIRD_TIER_BDT=5
ACTIVE_CAMPAIGN_DAYS=7
ACTIVE_CAMPAIGN_TASK_SCORE=1
ACTIVE_CAMPAIGN_REFERRAL_SCORE=5

## Provider check
CPAlead publisher offer sync/postback code is present. The live Offers provider aggregator now includes CPAlead when `CPALEAD_PUBLISHER_ID` is configured and `CPALEAD_ENABLED=true`; otherwise the existing behavior is unchanged. CPAlead postback remains server-to-server and idempotent.
