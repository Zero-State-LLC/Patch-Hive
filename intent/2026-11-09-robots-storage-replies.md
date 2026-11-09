# Intent

## Problem

The 2026-11-09 maker crawl skipped 2,334 files because their host answered 403 on robots.txt. Decision 3 calls that a refusal. For 777 of those files the 403 came from a file-storage service, in its own error format, and such services commonly answer 403 for a file that doesn't exist. Those hosts almost certainly have no robots.txt, and they haven't refused anyone. Make Noise's 64 manuals are among them.

Two fixes from the same crawl exist only locally: a robots.txt served as `application/octet-stream` was refused by the content-type check, which stopped Analogue Systems, and the Doepfer adapter read only a small part of the A-100 range.

## Proposed outcome

- A 403 on robots.txt whose body is a storage service's own error reply counts as a 404 (decision 66).
- A robots.txt served as `application/octet-stream` is read.
- The Doepfer adapter reaches the full A-100 range, and Analogue Systems has an adapter.

Out of scope: fetching the 777 files, which happens after this merges, and any catalog load.

## Affected users / systems

The catalog crawler (`data/synth-catalog/catalog_scrape.py`) and its adapter list. No product, API or database change.

## Constraints / non-goals

- Every other 401 or 403 on robots.txt stays a refusal, as do a bot check and a 401, 403 or 451 on a page. None of them reach a paid backend.
- The rule applies to robots.txt only. A file that itself answers 403 is still refused.
- Only the three replies seen in the crawl are recognised.

## Open questions

None. The owner chose this on 2026-11-09.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| 777 files sat on hosts whose robots.txt 403 was a storage error reply | `OBSERVED` | One robots.txt read per host on 2026-11-09, with the crawl's manifest for file counts |
| 1,557 files sat on hosts answering 403 with a firewall page or a bare "Forbidden" | `OBSERVED` | The same reads. These stay refused |
| Those storage hosts have no robots.txt | `INFERRED` | S3-style services commonly answer 403 for a missing file when listing is off. The reply can't show which |

## Author / date

- Author: Claude, for the owner
- Date: 2026-11-09
