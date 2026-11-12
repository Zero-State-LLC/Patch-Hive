# Evaluation corpus: permission note for Rig owners, 2026-11-08

**Draft. Counsel hasn't reviewed this. The notes at the end say what's settled and what isn't.**

There are two versions. Use the first when you take the photos, and the second when someone sends you a photo they took. A reply saying "I agree", with the boxes filled in, is enough to keep on file.

---

## Version 1: I photograph your Rig

Hi [name],

I run PatchHive, from Zero-State LLC. It reads a photo of a Eurorack Rig, works out which Modules are in it and where they sit, and makes a book of patches for that Rig. To measure how well it reads real Rigs, I'd like to photograph yours.

**What I'd like to do**

- Take about five photos of your Rig, in different light and with something partly in the way.
- Keep them while this test set is in use, for no more than three years unless you agree to longer, and use them to test and measure how well PatchHive reads photos.
- Send them to an outside AI service for that testing. Today that's NVIDIA, on a trial service. NVIDIA's terms for that service let it use what's sent to improve its products, including its AI models.

**What becomes public**

A list of the Modules in your Rig, where each one sits, and a fingerprint (a hash) of each photo will go in PatchHive's public code repository. The photos themselves won't, unless you tick the second box below. Your name never goes in the repository. If you tick the third box, it appears on a credits page on the PatchHive site, and I can take it off again.

**What I won't do**

I won't sell the photos, use them in advertising, or train an AI model on them myself.

**If you change your mind**

Tell me at [withdrawal address], and I'll remove your photos and stop using them. The Module list and fingerprints leave the current files, but stay in the repository's history. Test scores already worked out stay, as numbers only.

**Your answer**

- [ ] You may photograph my Rig and use the photos for testing, as above.
- [ ] You may also show one or more of them publicly, on the PatchHive site or in its public code repository.
- [ ] Credit me as: ____________ (leave blank for no credit)

I own this Rig, or I'm allowed to agree on behalf of whoever does.

Name: ____________  Date: ____________

---

## Version 2: You send me your photo

Hi [name],

I run PatchHive, from Zero-State LLC. It reads a photo of a Eurorack Rig, works out which Modules are in it and where they sit, and makes a book of patches for that Rig. To measure how well it reads real Rigs, I'm collecting photos from Rig owners, and I'd be glad to use yours.

**What I'd like to do**

- Keep your photo while this test set is in use, for no more than three years unless you agree to longer, and use it to test and measure how well PatchHive reads photos.
- Send it to an outside AI service for that testing. Today that's NVIDIA, on a trial service. NVIDIA's terms for that service let it use what's sent to improve its products, including its AI models.

**What you keep**

The photo stays yours. You're only giving me permission to use it this way, and you can still use it however you like.

**What becomes public**

A list of the Modules in your Rig, where each one sits, and a fingerprint (a hash) of the photo will go in PatchHive's public code repository. The photo itself won't, unless you tick the second box below. Your name never goes in the repository. If you tick the third box, it appears on a credits page on the PatchHive site, and I can take it off again.

**What I won't do**

I won't sell your photo, use it in advertising, or train an AI model on it myself.

**If you change your mind**

Tell me at [withdrawal address], and I'll remove your photo and stop using it. The Module list and fingerprint leave the current files, but stay in the repository's history. Test scores already worked out stay, as numbers only.

**Your answer**

- [ ] You may use my photo for testing, as above.
- [ ] You may also show it publicly, on the PatchHive site or in its public code repository.
- [ ] Credit me as: ____________ (leave blank for no credit)

I took this photo myself, or I hold the rights to it. It shows no people or private details.

Name: ____________  Date: ____________

---

## Where each item stands (not part of the note)

Researched 2026-11-08. This is a reading of public sources, not legal advice.

1. **Contact address: settled for now.** The owner has chosen one for withdrawals. It's left out of this public copy, so fill in `[withdrawal address]` before sending.
2. **Is an emailed yes enough, and whose photo is it? Yes, on US law.** The photographer owns the copyright ([17 U.S.C. 201](https://www.law.cornell.edu/uscode/text/17/201)), so owning the Rig doesn't make the photo yours or theirs. A non-exclusive permission [doesn't need a formal written transfer](https://www.dmlp.org/legal-guide/creating-written-contract-transfer-or-license-rights-under-copyright), though you should keep the reply. Other countries differ.
3. **Decision 33 for Version 2: still your call.** Version 1 fits today's rule. Version 2 needs the decision changed, and research can't settle that.
4. **NVIDIA: the old promise was too broad, so the note now discloses this.** [NVIDIA's trial terms](https://assets.ngc.nvidia.com/products/api-catalog/legal/NVIDIA%20API%20Trial%20Terms%20of%20Service.pdf) (v. 2025-09-19) cover internal testing and evaluation only (1.2, 1.4). They say content isn't stored or used after a session (2.3), and also that NVIDIA will collect submitted content to improve its products, including AI models (3.3). Counsel should read those two together. They bar uploading personal information (2.6, 4.3), which is why people stay out of frame. The note assumes a trial key, so check which kind PatchHive holds. Turning photo reading on in production (spec 009 T080) would need a paid subscription or a partner endpoint.
5. **How long photos are kept: a period is proposed.** [GDPR Article 5](https://gdpr-info.eu/art-5-gdpr/) sets no number, only no longer than necessary, and it applies where someone is identifiable. A Rig with no people may not count, but the name and email on this note do. The three years in the note is a proposal. Decision 26's 30 and 90 days cover photos uploaded in the product.
6. **What withdrawal costs: known.** Nothing is frozen yet, so today it's a manifest edit. After a freeze, the corpus hash runs through the run, proposal and receipt, so it means freezing, running, approving and signing offline (T083) again. [GDPR Article 7](https://gdpr-info.eu/art-7-gdpr/) says withdrawing must be as easy as agreeing and doesn't undo earlier use, which fits "scores stay". A free non-exclusive permission [can generally be revoked anyway](https://www.dmlp.org/legal-guide/creating-written-contract-transfer-or-license-rights-under-copyright).
7. **The "show publicly" box: no conflict, one risk.** Spec 009's "never public" sits under uploaded Rig photos, so it doesn't reach this box. [WIPO's overview](https://www.wipo.int/en/web/wipo-magazine/articles/ip-and-business-using-photographs-of-copyrighted-works-and-trademarks-35208) says a logo in a photo is a problem mainly if it implies sponsorship, and that incidental copyrighted work is generally fine. Panels are the subject of a Rig photo, not background, so that's the question for counsel. Say nothing that implies a maker endorses PatchHive.
8. **Credits page.** The note promises one on the site, and it doesn't exist yet. Names belong there rather than in the repo, because git history can't be taken back.

**Still for counsel:** how NVIDIA's 2.3 and 3.3 fit together, the three-year period, and panel art in public photos.
