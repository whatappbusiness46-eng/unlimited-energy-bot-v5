# Force Join + Global Gift Patch

## Included changes
- Added persistent database-backed Force Join ON/OFF control. The Admin Panel now shows the current state and toggles it without requiring a Render environment-variable edit.
- Both `/start` and the Verify Join callback use the same saved Force Join setting.
- Successful verification is saved to `groups_verified` and `verified_at`.
- The configured one-time Force Join reward (20 Points in this project) is credited once, guarded by `group_reward`.
- Existing users who already belong to every required group are marked verified on their next `/start`; the one-time reward is granted only if they have not received it before.
- Added Global Gift Center to Admin Panel. Admin enters Points, sees eligible count and total distribution, then explicitly confirms.
- Global gifts target only users with `groups_verified=True` and exclude banned/blacklisted accounts. This prevents gifts to users who have not completed verification.
- Each distribution has a unique batch ID stored per user to prevent duplicate credits from the same batch. Credits use the existing `add_balance` ledger path.
- Join campaign claim is released if the subsequent balance credit fails, so the member can retry instead of losing the claim.

## Important legacy-data limitation
Before this patch, the previous Verify Join flow did not persist `groups_verified`. Existing members are safely rechecked on their next `/start` while Force Join is ON. Until then, they are not included in Global Gift eligibility. This is intentional: the bot must not assume that unverified accounts completed all required joins.

## Verification
- Python compileall: passed.
- AST parse of all Python files: passed.
- ZIP integrity test: performed on the delivered archive.
- No live Telegram API / MongoDB / Render deployment test was possible in this environment. Provider APIs and actual member status still require live credentials and bot permissions.
