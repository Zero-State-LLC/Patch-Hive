---
title: "Alternative Sources for Modular Synthesizer Catalog Research"
version: "1.0.0"
last_updated: "2026-07-22"
type: "research-sources"
status: "active"
tags:
  - abraxas/research
  - abraxas/audio
  - modular-synth
  - data-sources
  - rate-limit-workaround
brier_relevance: 0.92
hyperstition_risk: 0.05
provenance: "OBSERVED (direct recommendations + known industry sources)"
---

# Alternative Sources for Modular Synthesizer Catalog Research

**Purpose:** Diversified list of 20 sources to avoid rate limits on ModularGrid ("modular grip"). Prioritizes official, retailer, community, archival, and review sources. Use in rotation for Phase 2–5 catalog work.

**Usage Recommendation:** 
- Primary for specs/pricing: Manufacturer sites + Perfect Circuit/Thomann
- Historical/context: MuffWiggler, Wikipedia, Attack Magazine
- Current availability: Reverb, Sweetwater, eBay completed listings
- Community validation: Reddit, YouTube reviewers (DivKid, Loopop, Omri Cohen)
- Always label provenance: **OBSERVED** (direct scrape), **INFERRED** (cross-referenced), **SPECULATIVE** (forum opinion).

## Diversified Source List (20 Sources)

### Official & Manufacturer Sources (High Trust)
1. **Manufacturer Official Websites** (e.g. makenoisemusic.com, intellijel.com, noiseengineering.us, doepfer.de, ericasynths.lv) — **OBSERVED** — Primary source for accurate specs, manuals, current firmware, and official module descriptions.
2. **Befaco.org** — **OBSERVED** — Excellent DIY documentation and build guides.
3. **Mutable Instruments GitHub** (archive) — **OBSERVED** — Open-source firmware and schematics for legacy Mutable modules and clones.
4. **Xaoc Devices** (xaocdevices.com) — **OBSERVED** — Detailed technical manuals for Batumi, Odessa, etc.

### Major Retailers (Pricing, Stock, Specs)
5. **Perfect Circuit** (perfectcircuit.com) — **OBSERVED** (user-recommended) — Excellent structured data: current pricing, stock status, detailed specs, category trees, and availability.
6. **Thomann / Thomann UK** (thomann.de or thomannmusic.com) — **OBSERVED** — Large inventory, customer reviews, current European pricing, and stock levels.
7. **Sweetwater** (sweetwater.com) — **OBSERVED** — Detailed product pages with specs, reviews, and US pricing.
8. **Schneider's Laden** (schneidersladen.de) — **OBSERVED** — Berlin-based specialist with deep Eurorack knowledge and current stock.

### Community & Forum Archives
9. **MuffWiggler Forum** (muffwiggler.com) — **OBSERVED** — Historical discussions, module comparisons, clone information, and discontinued product threads.
10. **Reddit r/modular & r/synthesizers** — **INFERRED** — Current user experiences, patch examples, and market sentiment (use search with `site:reddit.com`).
11. **ModularGrid** — **not used**. Never fetched (Danny 2026-10-17); earlier ModularGrid-derived values are archived and flagged `needs_reverify`.

### Review & Educational Sources
12. **DivKid Video Archive** (YouTube) — **OBSERVED** — In-depth module demos, calibration data, and feature breakdowns.
13. **Loopop** (YouTube) — **OBSERVED** — Technical deep-dives, spec measurements, and comparison videos.
14. **Omri Cohen** (YouTube / PatchFromScratch) — **OBSERVED** — Patch tutorials and real-world usage data.
15. **Attack Magazine / Synth Anatomy / Synthtopia** — **OBSERVED** — Professional reviews, interviews, and new release coverage.

### Archival & Market Data
16. **Reverb.com** — **OBSERVED** — Used market pricing, completed sales data, and availability of discontinued modules.
17. **eBay Completed Listings** — **OBSERVED** — Historical pricing trends for rare/vintage modules.
18. **Discogs** (for synth modules) — **OBSERVED** — Catalog data for physical releases and limited editions.
19. **VCV Rack Library** (library.vcvrack.com) — **OBSERVED** — Software implementations and specs for many Eurorack modules (great for digital clones).
20. **The Modular Synth Wiki / Books ("Patch & Tweak", "Modular Synthesis" by R. Hordijk)** — **OBSERVED** — Historical context, design theory, and non-Eurorack formats (Buchla, Serge, 5U).

### Bonus Long-Tail Sources (for Phase 4/5)
- **AI Synthesis, Befaco DIY kits, Thonk.co.uk** (DIY community)
- **Waveform Magazine, Perfect Circuit Blog**
- **Facebook Groups** (Eurorack, Buchla, Serge groups — observational only)
- **Manufacturer GitHub repos** (for open-source modules)

**Usage Strategy to Avoid Rate Limits:**
- Rotate 3-4 sources per brand.
- Cache pages locally via `web_extract` or browser tools.
- Use `site:` operator in web_search for targeted queries.
- For pricing: Perfect Circuit + Reverb + Thomann.
- For technical specs: Manufacturer site + DivKid/Loopop videos (transcribe key measurements).
- Always record provenance in YAML frontmatter.

**Next Step:** Use this list to source the remaining Phase 2 brands (Pittsburgh, Qu-Bit, Rossum, etc.) without hammering ModularGrid. Ready to continue extraction using these sources.

*Saved to references/alternative-sources.md. Continuing autonomous catalog work.*