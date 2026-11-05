# VirusTotal reanalysis, 2026-11-04

Project card: "[ops] VirusTotal reanalysis and the nine vendor false-positive reports".

Reanalysed by an agent on the owner's go-ahead. The report for `https://patch-hive.com/` is dated 2026-11-05 03:54:08 UTC.

| Target | Result |
|---|---|
| Domain `patch-hive.com` | No vendor flags it |
| URL `https://patch-hive.com/` | **9 vendors flag it**, 50 say clean |
| URL `https://api.patch-hive.com/` | No VirusTotal report exists, so nothing to reanalyse |

So the flags are on the site's root URL, not the domain. Deploying alpha.7 and alpha.8 didn't clear them.

## The nine reports

Each vendor needs its own report, and the owner submits them: these forms ask for an email address, a CAPTCHA or a sign-in. Suggested text for all of them: "owner-operated Eurorack documentation web app, no downloads".

| Vendor | Verdict | Where to report | Checked |
|---|---|---|---|
| BitDefender | Phishing | "Sample or URL Submit" form, linked from [Bitdefender's guide](https://www.bitdefender.com/business/support/en/77209-343057-submitting-sample-files-and-websites-for-analysis.html) | Search result only |
| CRDF | Malicious | [False positive procedure](https://threatcenter.crdf.fr/false_positive.html) | Page loads |
| CyRadar | Phishing | [Contact page](https://cyradar.com/contact/); no dedicated form found | Page loads |
| Forcepoint ThreatSeeker | Phishing | Site Lookup tool, per [Forcepoint's article](https://support.forcepoint.com/s/article/How-To-Submit-Uncategorized-Sites); needs a sign-in | Search result only |
| Fortinet | Phishing | [Web Filter rating request](https://www.fortiguard.com/faq/wfratingsubmit) | Page loads |
| G-Data | Phishing | [Submit a file, app or URL](https://www.gdata.de/help-en/general/GeneralInformation/submitFileAppURL/) | Search result only |
| Kaspersky | Phishing | [OpenTIP portal](https://opentip.kaspersky.com/); confirm it takes a dispute before relying on it | Page loads |
| Lionic | Phishing | [Report False Positive](https://www.lionic.com/supports/report-false-positive/), "False Positive URL on VirusTotal"; has a reCAPTCHA | Page read |
| Sophos | Phishing | [Support submission page](https://support.sophos.com/support/s/filesubmission); confirm it takes URLs | Page loads |

"Page loads" means the page answered and its title fits. None of these forms has been submitted. Re-run the reanalysis a few days after the reports go in.
