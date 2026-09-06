# VIP ON/OFF Fix

Fixed the Admin **VIP Purchase ON/OFF** control.

## What was broken
The VIP setting functions called `get_setting()` / `set_setting()`, but those functions do not exist in `database.py`. As a result, the read silently fell back to ON and the save returned False.

## What is fixed
- VIP setting is now stored in MongoDB `bot_settings` document (`_id: "main"`).
- Admin button now displays the current state: `💎 VIP Purchase: 🟢 ON` / `🔴 OFF`.
- The switch is checked when opening a VIP purchase.
- The switch is checked again when confirming a purchase, preventing old confirmation buttons from bypassing the OFF state.
- Existing VIP memberships are not revoked when purchases are turned OFF.

## Deploy
Upload this project to GitHub/Render and redeploy. No new environment variable is required.
