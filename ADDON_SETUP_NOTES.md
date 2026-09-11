# Tasks + CPAGrip + Shortlinks patch notes

## Already included
- Admin-managed Tasks: add/update, enable/disable, delete.
- Task format: `id|title|description|url|reward|cooldown|xp|energy|task_type|audience|verification`. Audience: `normal`, `vip`, or `both`. Verification: `telegram_join` (public t.me links) or `manual` (not auto-rewarded). Tasks are permanently one-time per user; cooldown does not reset a completed task.
- Referral qualification: signup attribution is pending; the first qualifying task releases the referral reward once.
- Referral anti-duplicate markers and milestone markers.
- Default referral milestones: 5=100, 10=250, 25=700, 50=1500, 100=3500 Points.
- Help contact: @mdrifatowner05.
- CPAGrip live offer feed in Earn > CPA Offers.
- CPAGrip postback endpoint: `/cpagrip/postback`.
- CPAGrip conversion credit requires the configured postback password and is idempotent.
- Admin can hide/delete cached CPAGrip offers.
- Admin-managed Shortlinks with cooldown and enable/disable/delete.


## CPAGrip setup
1. Put the real CPAGrip API key, offer-feed URL, and Global Postback password in Render Environment Variables.
2. In CPAGrip Global Postback, set the URL to:
   `https://YOUR-RENDER-SERVICE.onrender.com/cpagrip/postback`
3. The bot uses the user's Telegram ID as the offer `tracking_id` so the postback can map a conversion back to the user.
4. Do not put provider keys/passwords in GitHub or in chat.

## Deployment
Replace the matching files in the repository with this patch, keep the same MongoDB database, then redeploy. Do not reset the database.

## 🇧🇩 CPAlead Bangladesh Tasks

The bot now has a separate **🇧🇩 BD Tasks** section under Earn Center. It pulls CPAlead offers targeted to Bangladesh (`country=BD`), passes the Telegram user ID as `subid`, and credits member Points only after a verified CPAlead server-to-server postback.

### Render ENV

Add these variables:

```env
CPALEAD_ENABLED=true
CPALEAD_PUBLISHER_ID=YOUR_CPALEAD_PUBLISHER_ID
CPALEAD_POSTBACK_PASSWORD=YOUR_LONG_RANDOM_POSTBACK_PASSWORD
CPALEAD_USER_REWARD_PERCENT=40
CPALEAD_POINTS_PER_USD=1000
CPALEAD_BD_TASK_LIMIT=20
```

### CPAlead postback

Configure the CPAlead publisher postback to:

```text
https://YOUR_RENDER_DOMAIN/postback/cpalead?subid={subid}&lead_id={lead_id}&campaign_id={campaign_id}&campaign_name={campaign_name}&payout={payout}&country_iso={country_iso}&password={password}
```

Use the same value in `CPALEAD_POSTBACK_PASSWORD` and CPAlead's postback password setting. Keep the placeholders exactly as shown so CPAlead replaces them with the real conversion values.

### Reward calculation

Default member reward is 40% of the provider payout, converted at 1000 Points per USD. Example: a $1.00 provider payout credits 400 Points before any membership multiplier. Provider payout is hidden from members.

### Safety

Only CPAlead offers returned for Bangladesh by the API are shown in the BD Tasks section. Conversion credit is idempotent by `lead_id`; duplicate callbacks do not credit twice. Reversals remove the previously credited Points and record provider debt if the member no longer has enough balance.


## Offerwall.me-only task categories
The Earn > Tasks screen now groups the current Offerwall.me task inventory into:
- 🟢 Easy Tasks (signup/register/follow/join/visit/click-style offers when the provider marks them that way)
- 📱 App Install (install/CPI/app offers)
- 🎬 Video Ads (video/rewarded-ad offers when Offerwall.me returns them)
- 📝 Surveys
- 💰 Other Tasks

The bot does not invent provider offers. Categories are inferred from Offerwall.me metadata/title/instructions, so a category is shown only when the current provider inventory contains a matching task.

Important: Offerwall.me's public homepage currently states that it has paid $24.5K to publishers, but that is the provider's own published figure, not an independent guarantee of future payout. Keep the verified S2S postback configured before crediting member Points.
