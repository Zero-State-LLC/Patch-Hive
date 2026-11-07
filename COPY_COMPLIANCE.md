# Copy Compliance

This document tracks publishing copy constraints for PatchHive.

## Required Canon Copy Used
- "PatchHive is free to explore. You only pay when you export something you want to keep."
- "You'll receive free credits if your friend makes their first purchase."

## Allowed copy
- "Publish"
- "Unlisted"
- "Public"
- "Allow download"

## Forbidden copy
Do not use the following in publishing surfaces:
- premium
- pro
- subscribe
- upgrade
- commission
- affiliate

## Forbidden Terms Scan
Checked the dashboard/referral copy in `frontend/src/pages/Account.tsx`, and the buying and plan copy in `frontend/src/components/AccountCommerce.tsx` and `frontend/src/lib/commerce.ts`. `backend/tests/unit/test_copy_compliance.py` scans all three.
- Forbidden terms not used: upgrade, premium, pro, subscribe, commission, affiliate.
- So a paid plan is named by what it gives ("25 credits each billing period"), and the button says "Start this plan". The tier names stay in the data.

## Current publishing UI usage
- `/account`: Publish an export, Unlisted, Public, Allow download
- `/publish`: Publish, Unlisted, Public, Allow download
- `/p/{slug}`: Report
- `/gallery`: Gallery

## Notes
- Credits section uses neutral terms only (credits, balance, history).
- Referral copy uses non-monetary framing and follows the canon referral line.
