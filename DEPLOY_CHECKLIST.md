# Deployment checklist

1. Create a Render Web Service.
2. Add all required environment variables from `.env.example`.
3. Set `PUBLIC_BASE_URL` to the service's public HTTPS URL.
4. Confirm MongoDB Network Access allows the Render service to connect.
5. Confirm the Telegram bot token is valid.
6. Configure CPAGrip offer API/feed using the provider's documented endpoint.
7. Configure CPAGrip postback with the exact user-id/event-id/reward parameters.
8. Configure the postback secret/signature exactly as documented.
9. Test one provider conversion in a controlled/test environment.
10. Verify: provider callback -> duplicate check -> MongoDB event -> user balance -> transaction.
11. Configure Offerwall.me offers/tasks/shortlinks and verified postback.
12. Do not credit users merely because they clicked a shortlink or pressed Verify.
13. Test withdrawal/admin approval before public launch.


### Task verification
Task verification is OFF by default. Set Render environment variable `TASK_VERIFICATION_ENABLED=true` to enable configured verification checks; leave it `false` to allow admin-controlled task completion without automatic verification.

## 🇧🇩 CPAlead BD Tasks
- Add `CPALEAD_ENABLED=true`
- Add `CPALEAD_PUBLISHER_ID`
- Add `CPALEAD_POSTBACK_PASSWORD`
- Add `CPALEAD_USER_REWARD_PERCENT=40`
- Add `CPALEAD_POINTS_PER_USD=1000`
- Add `CPALEAD_BD_TASK_LIMIT=20`
- Configure CPAlead publisher postback to `/postback/cpalead` using the macros documented in `ADDON_SETUP_NOTES.md`.
- Test one real/sandbox conversion and confirm the Points are credited once and duplicate callbacks are ignored.


## Offerwall.me-only Tasks
- Keep `OFFERWALLME_ENABLED=true`.
- Keep the existing Offerwall.me API key, bearer token, country and postback secret in Render ENV.
- Offerwall.me tasks are grouped into Easy Tasks, App Install, Video Ads, Surveys and Other Tasks based on provider metadata/title.
- Video Ads will appear only when Offerwall.me's current task inventory returns a matching video/rewarded-ad offer.
- Do not hardcode fake task links or rewards.
