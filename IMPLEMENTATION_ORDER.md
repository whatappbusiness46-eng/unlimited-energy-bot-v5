# Future implementation order

Build future income features one at a time and test the existing bot after every change.

### Phase 1 — Revenue reliability
- Add additional legitimate CPA providers only when their API/postback terms permit the traffic model.
- Keep provider conversion IDs unique and idempotent.
- Keep member rewards independent from provider payout.

### Phase 2 — Advertiser marketplace
- Admin creates campaigns.
- Campaign has URL, task type, audience, reward, daily cap, total cap, start/end time and approval mode.
- Members see only member reward and task instructions.
- Admin sees campaign cost and performance.

### Phase 3 — Analytics
- Revenue, member rewards, withdrawals, provider conversions and net margin.
- Daily/weekly/monthly reports.

### Phase 4 — Growth
- Referral tiers, retention bonuses and VIP perks that are funded by real revenue.
