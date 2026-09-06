# Tasks + CPAGrip + Shortlinks patch notes

## Already included
- Admin-managed Tasks: add/update, enable/disable, delete.
- Task format: `id|title|description|url|reward|cooldown|xp|energy`.
- Referral qualification: signup attribution is pending; the first qualifying task releases the referral reward once.
- Referral anti-duplicate markers and milestone markers.
- Default referral milestones: 5=100, 10=250, 25=700, 50=1500, 100=3500 Points.
- Help contact: @mdrifatowner05.
- CPAGrip live offer feed in Earn > CPA Offers.
- CPAGrip postback endpoint: `/cpagrip/postback`.
- CPAGrip conversion credit requires the configured postback password and is idempotent.
- Admin can hide/delete cached CPAGrip offers.
- Admin-managed Shortlinks with cooldown and enable/disable/delete.
- ShrtFly/ShrinkMe API link creation is supported when their exact API URL/token are configured.

## Important provider limitation
ShrtFly/ShrinkMe link creation does not itself prove that a user completed a monetized conversion. The bot therefore must not award a provider reward merely because a user presses a client-side Verify button. Use a provider-supported server-to-server completion mechanism before enabling automatic rewards for a provider.

## CPAGrip setup
1. Put the real CPAGrip API key, offer-feed URL, and Global Postback password in Render Environment Variables.
2. In CPAGrip Global Postback, set the URL to:
   `https://YOUR-RENDER-SERVICE.onrender.com/cpagrip/postback`
3. The bot uses the user's Telegram ID as the offer `tracking_id` so the postback can map a conversion back to the user.
4. Do not put provider keys/passwords in GitHub or in chat.

## Deployment
Replace the matching files in the repository with this patch, keep the same MongoDB database, then redeploy. Do not reset the database.
