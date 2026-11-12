# Module jack lists, 2026-11-09

`overlays/module-jacks-v1.json` proposes jack lists for 224 Modules: 1,606 jacks from 65 makers, read from 147 user manuals and 77 maker pages. Before this, 2 of the 3,379 public Modules declared jacks, so Patch Books printed role names such as "Audio Out". Both databases now hold these lists, as recorded under [Loads](#loads).

## How the lists were chosen

`scripts/read_module_jacks.py` read each Module's maker page and user manual from the 2026-11-09 crawl, twice, with differently worded prompts, on Claude Haiku 5.5 through OpenRouter. That was 6,356 readings for $3.87. All came back usable.

A Module was proposed only when, for one document:

- both readings called the list complete
- both agreed on every jack's direction and signal
- each jack's quote was found in the document
- no two jacks shared a name
- the list had at least one output
- the list didn't look like one channel of a multi-channel Module

Of the 2,514 Modules read, 224 passed. Most of the rest fell short because the document doesn't name every jack.

## Hand check

25 accepted lists were compared with their documents, 10 from a 100-Module test and 15 chosen at random from the full run.

- 23 were right. For the 15 from the full run only the jack-related lines of each document were read, and two or three of those lists could be confirmed only in part.
- 2 were incomplete: Mutable Streams and Bard VTG are dual-channel, and both readings listed one channel. The last check above was added because of them, and took the count from 240 to 230.
- Code review on the pull request then found a third: shkrjn's Decay manual says two envelopes but describes one set of jacks. Widening the check took the count to 224. The check also removes some good lists, such as Pittsburgh Modular's LFO2, and can't catch every case.

## Limits

- "Complete" means the document appears to cover every jack. No list was checked against a physical panel.
- A document can describe a different revision from the row. A page for a later version (Rev2, II, Mk2) is no longer matched, but a manual can still cover a sibling revision, as with µVCA and the µVCA II manual.
- Two readings by one model catch slips, not a mistake both make.

## Loads

The owner approved each load on its hashes. Both ran through `db-load.yml` in `apply` mode on 2026-11-10 UTC, staging first, with the same `plan_hash` `2dc0e298e2255efb59578f1848d3ecf79970d2a9877d631bb0a3da40cdc6281a` and `inputs_hash` `a18108914c293f5e1a87e9278976626547894ff01450db9fb28430fe89a8e086`.

| Database | Run | Commit | Result |
|---|---|---|---|
| Staging | [42738704964](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42738704964) | `c3aa686` | 224 lists filled, 0 conflicts, no inserts, no destructive SQL |
| Production | [42752081150](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/42752081150) | `88efb73` | 224 lists filled, 0 conflicts, no inserts, no destructive SQL |

On each host `catalog_load_runs` went from 1 to 2 and `catalog_load_changes` from 39 to 263, one change per list. No other table's row count changed.

Reading each host's public API after 0.3.0-alpha.20 was deployed, `/api/modules` has 3,379 rows, 226 of them declare jacks, and all 224 lists are served exactly as the overlay has them.

To undo a load, run `db-load.yml` with its run ID as `rollback_run_id`, which restores the empty lists. No rollback has been run on a deployed database.

Engine 1.3.0 (#390) went live with that deploy. It takes a filter's lowpass output for a generic audio cable, which changes the jack chosen for 5 of these lists and not the lists themselves.

## Files

| File | SHA-256 |
|---|---|
| `data/synth-catalog/overlays/module-jacks-v1.json` | `9d37ec3945467db6264df02e65cb59badcfe11f65f4aa2b282008c4000b24bf1` |
| Private proposal, with the quote behind every jack (not in this repository) | `1818174f7f009f957bddd04c20177a6049c414fd6fbd663480df361111c79de7` |

The loader fills `io_ports` only where it's empty, and a list that differs from a stored one is reported as a conflict and left alone (spec 003 FR-041). Each load needs the owner's yes on its plan and inputs hashes.
