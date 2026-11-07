# Dashboard Implementation

## Routes (Frontend)
- `/account` → `frontend/src/pages/Account.tsx`
  - Credits balance + ledger
  - Exports list
  - Referrals summary + copy link
  - Profile (display name + avatar URL)
- `/leaderboards/modules` → `frontend/src/pages/LeaderboardsModules.tsx`
  - Popular / Trending (30d) tabs

## API Endpoints (Backend)
### Auth / Identity
- `GET /api/community/users/me`
  - Returns current user profile.

### Account Dashboard
- `GET /api/canon/credits/summary`
  - Returns the balance and recent entries from the canonical ledger. `GET /api/me/credits` is gone (spec 004 FR-009).
- `GET /api/me/exports`
  - Returns recent `export_records` for the current user.
- `GET /api/me/referrals`
  - Returns the referral code and link, pending and rewarded counts, credits earned and recent masked referrals (spec 004 FR-031).

### Leaderboards (Aggregate-Only)
- `GET /api/leaderboards/modules/popular`
  - Counts module appearances in **public racks** using `rack_modules`.
- `GET /api/leaderboards/modules/trending?window_days=` (default 30)
  - Counts module appearances in **public racks** created within the time window.
- Results cached in-memory for ~30 minutes.

## Schemas (Backend)
- `CreditLedgerEntry` (`credit_ledger_entries`)
  - `user_id`, `entry_type`, `amount`, `description`, `created_at`
- `ExportRecord` (`export_records`)
  - `user_id`, `export_type`, `entity_id`, `run_id`, `unlocked`, `license_type`, `created_at`
- `Referral` (`referrals`)
  - `referrer_user_id`, `referred_user_id`, `status`, `rewarded_at`, `created_at`
- `User`
  - Added `display_name` and `referral_code`.

## Notes
- Referral codes are generated per user and stored on the user record; links are stable.
- Referral summary masks referred user IDs (e.g., `user-****1234`).
- Leaderboards return aggregate module counts only (no user IDs, no patch content telemetry).
