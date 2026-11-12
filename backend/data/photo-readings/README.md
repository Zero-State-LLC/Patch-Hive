# Recorded photo answers (spec 009)

Staging reads a Rig photo by replaying its recorded answer from this folder, with no network
(`PHOTO_READING_PROVIDER=recorded`, `PHOTO_READING_RECORDINGS_DIR=/app/data/photo-readings` in
`edge/api/wrangler.jsonc`). The folder ships in the API image. Production never reads it.

A recording is named by the SHA-256 of the photo file as uploaded: `<sha256>.json`. It holds every
Sighting in the photo, as a provider would answer:

```json
{
  "provider_version": "recorded-walkthrough-1",
  "sightings": [
    {
      "box": {"x": 0.0, "y": 0.05, "w": 0.1, "h": 0.9},
      "kind": "module",
      "row_index": 0,
      "start_hp": 0,
      "hp": 12,
      "candidates": [{"maker": "Mutable Instruments", "name": "Plaits", "score": 0.97}]
    }
  ]
}
```

Name each candidate by `maker` and `name`, not by `module_id`: catalog ids differ between
databases, and names resolve against whichever catalog reads the photo, by the same rule as a
live provider (`CatalogNames` in `backend/evidence/readings.py`). A name that fits no Module, or
two, is dropped, never guessed. `kind` is `module`, `blank_panel`, `unknown` or `not_eurorack`,
and only a `module` names candidates. `row_index` counts from the first row the photo covers.

The staging walkthrough (`scripts/staging/photo_walkthrough.py`, spec 009 T060) uploads a fixture
photo and refuses to start unless this folder holds its recording.
