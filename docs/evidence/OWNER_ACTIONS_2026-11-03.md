# Owner actions, 2026-11-03

This packet follows the remediation of the 39 Backlog cards on [Project #8](https://github.com/orgs/Zero-State-LLC/projects/8).

- **Board:** 10 cards closed with evidence. Every other card now says what it waits on: In review (an open PR), Ready (agent work proposed as a session), or Backlog marked "Blocked: waiting on …".
- **This packet** lists every remaining step that needs you, in dependency order. It supersedes the open items of [OWNER_ACTIONS_2026-11-02.md](OWNER_ACTIONS_2026-11-02.md) and links that guide's command blocks rather than repeating them.

## 0. Land the remediation PRs

`enforce_admins` is on, so the agent cannot merge.

1. Turn it off (your choice from 2026-11-03; changing branch protection stays yours):

   ```bash
   gh api -X DELETE repos/Zero-State-LLC/Patch-Hive/branches/main/protection/enforce_admins
   ```

2. The agent merges each PR when its CI is green:

   | PR | What it does |
   |---|---|
   | #241 | Board mirror and release priority |
   | #242 | Docs truth after the alpha.6 deploy |
   | #243 | F5: rig builder on canon, scanner fix |
   | #244 | Live smoke suite |
   | #245 | `release.yml` skips existing releases |
   | #246 | Accessibility pre-pass and log |
   | #247 | Branch triage |
   | #248 | 008 pin driver |
   | this PR | The packet itself |

3. Turn `enforce_admins` back on:

   ```bash
   gh api -X POST repos/Zero-State-LLC/Patch-Hive/branches/main/protection/enforce_admins
   ```

## 1. Start the three proposed sessions

They appear as session cards in the Claude Code conversation. Each opens PRs and the agent merges them.

| Session | Cards it moves | What it produces |
|---|---|---|
| `specs-prep` | 001–004 T002/T010/T090 prep; [005] Spec Kit gaps | refreshed status tables, DRAFT plans, the 002 flag-off test, the 004 Machine C correction draft, the 005 Workflows and transition table |
| `catalog-offline` | [catalog] 20 two-category rows; [003 T031]; [decision] maker permission | an offline category overlay, feed adapters that keep store taxonomy, a decision brief and a held stealth-proxy PR |
| `drills` | [beta] acceptance suite; [beta] backup/restore | a CI acceptance job, a staging acceptance workflow, a reconcile CLI, a backup/restore drill |

## 2. Confirm specs 001–004 (T001)

Use the checklists in [OWNER_ACTIONS_2026-11-02.md § Decisions 1](OWNER_ACTIONS_2026-11-02.md). Each sitting takes about 45–90 minutes, and 003 is the shortest.

After each confirmation, the agent ticks T001, finalises plan.md (T002), encodes or de-scopes the open transition rows (T010), and converges (T090). For 004, approve or reject the Machine C correction (`subscription_created` → `invoice.paid`) that `specs-prep` drafts.

## 3. The evaluation chain (specs 005, 007, 006, 008)

This one chain unblocks 7 cards: 005 T061/T062/T070, 007 T020b, 006 T060b, 008 T050b and #21.

1. **Corpus (007 T010b).** Supply 50–100 rights-cleared module photos with labels; open web search found 2 usable images in 300. The validator must say `ADMITTED_FOR_BASELINE`.
2. **Run, propose, approve, pin, sign** with `scripts/staging/run_007_evaluation.py`: commands in [§ Item 2](OWNER_ACTIONS_2026-11-02.md). Signing (T083) uses your offline key `approver-2026-11`.
3. **Enable on staging (007 T085, new in #242).** The flag step now comes after signing, because the container refuses provider flags without a signed receipt. The agent commits the receipt and the staging vars; you deploy staging:

   ```bash
   cd edge/api && npx wrangler deploy --env staging
   ```

4. **006 T060b:** choose whether to verify the wired provider (NVIDIA through the Clef adapter) or to run a Clef evaluation too. Then re-run the check in [§ Item 3](OWNER_ACTIONS_2026-11-02.md).
5. **Done 2026-11-04:** the walkthrough passed at the deployed `6c234a6` (v0.3.0-alpha.7, run [41768209990](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/41768209990); [receipts](STAGING_RECEIPTS_2026-11-04.md)). For a later re-run at a newer deployed SHA:

   ```bash
   gh workflow run staging-walkthrough.yml --repo Zero-State-LLC/Patch-Hive
   ```

6. **Pin the readiness docs (008 T050b).** The driver comes from #248:
   1. Put the walkthrough's source SHA into both readiness docs. Done for `6c234a6`; redo it only after a newer walkthrough.
   2. Run the three commands:

      ```bash
      python scripts/staging/pin_readiness_008.py check --bundle <bundle> --enablement-receipt <dir>/receipt.json --enablement-signature <dir>/signature.json
      python scripts/staging/pin_readiness_008.py pin --bundle <bundle> --enablement-receipt <dir>/receipt.json --enablement-signature <dir>/signature.json --key ~/patchhive-approver/approver-2026-11.pem --pinned-by approver-2026-11 --out docs/evidence/receipts/readiness-pin-<date>.json
      python scripts/staging/pin_readiness_008.py replay --bundle <bundle> --pin docs/evidence/receipts/readiness-pin-<date>.json
      ```

   3. `replay` exiting 0 means `BETA_ELIGIBLE`. Close #21 then.

## 4. Dispatches (each writes to staging, or reads production)

- **After every deploy:** `gh workflow run smoke.yml -f target=staging`, then `-f target=production` after a production deploy (#244).
- **Acceptance and backup/restore drills:** dispatch the workflows the `drills` session adds; its PR lists the commands.
  - If the drills should use Neon child branches, add a `NEON_API_KEY` secret.
  - A production drill needs your explicit yes.

## 5. Decisions

- **Maker permission and proxy tier.** Decide whether official spec pages count as publication, or whether to ask makers, and sign off the proxy tier. Until then, catalog work stays offline: no page or feed reads.
- **Catalog taxonomy:**
  - put about 21 video modules in a new VIDEO category, or in UTIL;
  - decide whether to retire about 11 power-supply rows;
  - add an approvals entry, with a cap, for any paid T031 remainder.
- **Catalog loads:** a go-ahead for each `db-load.yml` apply, with the reviewed plan and inputs hashes.
- **Branches** ([BRANCH_TRIAGE_2026-11-03.md](BRANCH_TRIAGE_2026-11-03.md)):
  - delete the 12 whose patches are already in `main`;
  - check the 20 believed landed elsewhere;
  - keep or drop the 5 that never landed;
  - optionally turn on "Automatically delete head branches".
- **Release:** merge the open Release Please PR (#240 today) right before a deploy that ships code, so the tag matches what runs. The beta line is decided: `0.3.0-beta.1` via a `Release-As` footer at beta exit.
- **Optional:** make `frontend-e2e` a required check.

## 6. Hands-on

- **Accessibility:** the screen-reader and PDF pass, using the log template in [docs/ACCESSIBILITY.md](../ACCESSIBILITY.md) (VoiceOver/Safari, NVDA/Firefox, PDF reading order). The automated pre-pass already runs on CI (#246).
- **Cloudflare and GitHub** (commands in [OWNER_ACTIONS_2026-11-02.md § Operations 3 and 4](OWNER_ACTIONS_2026-11-02.md)):
  - T055b: R2 token scope and the restart-persistence check;
  - T101b: protect the `production` environment.
- **Production:** a real sign-up, plus the VirusTotal reanalysis ([§ Decisions 4](OWNER_ACTIONS_2026-11-02.md)).
