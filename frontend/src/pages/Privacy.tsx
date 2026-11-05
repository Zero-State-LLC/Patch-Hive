/**
 * Privacy notice: what the service holds today, stated as facts and marked as not yet reviewed
 * by counsel (owner decisions 24 to 26, 32 and 33, 2026-11-04). Each claim was checked against
 * the code; a change to the behaviour it describes has to change this page too.
 */
import { Link } from "react-router-dom";
import "./Privacy.css";

const LAST_UPDATED = "2026-11-04";
const KEPT_AFTER_DELETION = "Kept, including after account deletion. No period decided.";

/** Plain strings: a stacked table cell lays out its label and one text node on a grid. */
const DATA_HELD: { data: string; where: string; kept: string }[] = [
  {
    data: "Account: email address, username, display name, avatar URL, bio, password hash and hashed session tokens",
    where: "Neon",
    kept: "Until you delete the account. See Deleting your account.",
  },
  {
    data: "Rig photos, re-encoded as JPEG",
    where: "Cloudflare R2, with a working copy on the API's temporary disk",
    kept: "30 days by default, 90 at most. The file can stay longer. See Rig photos.",
  },
  {
    data: "Photo records: file hash, size, retention dates and the classification record made at upload",
    where: "Neon",
    kept: "Kept after the photo is deleted. No period decided.",
  },
  {
    data: "Rigs, rig revisions, generation runs, patches and their receipts",
    where: "Neon",
    kept: KEPT_AFTER_DELETION,
  },
  {
    data: "Credit ledger, referral rows and export records",
    where: "Neon",
    kept: KEPT_AFTER_DELETION,
  },
  {
    data: "Exported files",
    where: "Cloudflare R2",
    kept: KEPT_AFTER_DELETION,
  },
  {
    data: "Payment event records: event ID and type, payload hash, status and reason code",
    where: "Neon",
    kept: "No period decided. There are no sales today.",
  },
  {
    data: "Reports on published items: reason, details and, if signed in, the reporter's account",
    where: "Neon",
    kept: "No period decided. Publishing is off on production, so reports can't be filed today.",
  },
  {
    data: "Admin audit records",
    where: "Neon",
    kept: "Append-only. No period decided.",
  },
  {
    data: "Request logs: IP address, method, path and status code",
    where: "Cloudflare",
    kept: "No period decided.",
  },
];

export default function PrivacyPage() {
  return (
    <section aria-labelledby="privacy-title" className="privacy-notice">
      <header className="workspace-header">
        <div>
          <h1 id="privacy-title">Privacy notice</h1>
          <p className="muted">
            What PatchHive holds about you, where it&apos;s kept and what deleting an account does.
            Zero-State LLC operates PatchHive. This page describes the production service at
            patch-hive.com as it&apos;s built today.
          </p>
          <p className="privacy-status">
            <span className="status-chip status-chip--warning">Not yet reviewed by counsel</span>
            <span>
              Last updated <time dateTime={LAST_UPDATED}>{LAST_UPDATED}</time>
            </span>
          </p>
        </div>
      </header>

      <div className="ops-page">
        <section className="ops-section" aria-labelledby="privacy-collects">
          <h2 id="privacy-collects">What PatchHive collects</h2>
          <p>
            The sign-up form asks for a username, an email address and a password. PatchHive stores
            the password only as an Argon2id hash. Your username is also your display name until you
            change it, and each account gets a generated referral code. PatchHive doesn&apos;t
            confirm the email address or send email today.
          </p>
          <p>
            The account page lets you set a display name and an avatar URL. The API also accepts a
            bio. As you use the app, PatchHive stores the rigs and rig photos you add, and the
            patches, runs and exports made from them.
          </p>
        </section>

        <section className="ops-section" aria-labelledby="privacy-data">
          <h2 id="privacy-data">Data held</h2>
          <div className="ops-table-wrap">
            <table className="data-table ops-table-stack privacy-table">
              <caption className="visually-hidden">
                The data PatchHive holds, where it is stored and how long it is kept
              </caption>
              <thead>
                <tr>
                  <th scope="col">Data</th>
                  <th scope="col">Where</th>
                  <th scope="col">How long</th>
                </tr>
              </thead>
              <tbody>
                {DATA_HELD.map((row) => (
                  <tr key={row.data}>
                    <th scope="row">{row.data}</th>
                    <td data-label="Where">{row.where}</td>
                    <td data-label="How long">{row.kept}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="ops-section" aria-labelledby="privacy-photos">
          <h2 id="privacy-photos">Rig photos</h2>
          <p>
            A photo you upload is decoded and saved again as a JPEG, at most 4096 pixels on its long
            side. That removes EXIF data, including any GPS location, as well as XMP data and colour
            profiles, and any JPEG comment. Re-encoding doesn&apos;t change what the picture shows,
            so anything visible in it stays.
          </p>
          <p>
            The site&apos;s upload form keeps photos for 30 days and offers no other choice. The API
            accepts 1 to 90 days. Earlier versions of the API accepted up to 365 days, and a photo
            stored with a longer period keeps it until it expires or is deleted.
          </p>
          <p>
            An expired photo is refused when the system tries to read it, but its file stays in
            storage until the expiry job runs. That job isn&apos;t scheduled yet. It runs only when
            an operator starts it, so a file can stay after its period ends.
          </p>
          <p>
            The API can delete one of your photos at once. Its file goes unless another stored
            upload is the identical file. The site has no button for this yet. Deleting a rig
            doesn&apos;t remove its photos, and the site has no button for that either.
          </p>
        </section>

        <section className="ops-section" aria-labelledby="privacy-access">
          <h2 id="privacy-access">Who can see it</h2>
          <ul className="privacy-list">
            <li>
              Anyone can read your username, display name, avatar URL, bio and account creation date
              through the API, without signing in. Your email address isn&apos;t included.
            </li>
            <li>
              Accounts with an operator role (Admin, Ops, Support or ReadOnly) can read the user
              list, including email addresses, and rigs that aren&apos;t public.
            </li>
            <li>
              Rigs are private by default, and the site has no control to make one public. The API
              can mark a rig public, and anyone can then read it.
            </li>
            <li>Publishing to a public gallery is off on production.</li>
          </ul>
        </section>

        <section className="ops-section" aria-labelledby="privacy-deleting">
          <h2 id="privacy-deleting">Deleting your account</h2>
          <p>
            You can delete your account from the <Link to="/account">account page</Link>. It asks
            you to type your username and current password first.
          </p>
          <h3>What deletion does</h3>
          <ul className="privacy-list">
            <li>Signs you out everywhere and revokes every session.</li>
            <li>
              Replaces or clears your email address, username, display name, avatar URL, bio,
              password hash and referral code.
            </li>
            <li>
              Deletes your comments, votes, patch overlays, patch annotations and style recipes.
            </li>
            <li>
              Hides your rigs, makes them private and clears their names, descriptions and tags.
            </li>
            <li>
              Sets any publications to removed, clears their text and turns off their downloads, and
              detaches you from any reports you filed.
            </li>
            <li>
              Expires your photos and deletes their files at once, unless another stored upload is
              the identical file. If storage fails, the file waits for the expiry job, which
              isn&apos;t scheduled yet.
            </li>
            <li>Writes one audit record that holds counts only.</li>
          </ul>
          <h3>What deletion keeps</h3>
          <p>These stay, tied to the anonymised account:</p>
          <ul className="privacy-list">
            <li>Credit ledger, referral rows, export records and exported files.</li>
            <li>Rig revisions, generation runs, patches and their receipts.</li>
            <li>Photo records and classification records.</li>
            <li>Admin audit records.</li>
          </ul>
          <p>
            Text inside these rows isn&apos;t cleared. Patch names and descriptions, for example,
            stay as they were. Deletion doesn&apos;t reach backups or logs, or anything at a payment
            or AI provider.
          </p>
        </section>

        <section className="ops-section" aria-labelledby="privacy-services">
          <h2 id="privacy-services">Outside services</h2>
          <ul className="privacy-list">
            <li>
              <strong>Cloudflare</strong> serves the site, runs the API, stores files in R2 and
              holds request logs. It also adds its Web Analytics script to pages, and the script
              reports to cloudflareinsights.com.
            </li>
            <li>
              <strong>Neon</strong> hosts the database.
            </li>
            <li>
              <strong>Google Fonts</strong>: pages load their fonts from fonts.googleapis.com and
              fonts.gstatic.com, so your browser sends those requests to Google.
            </li>
            <li>
              <strong>GitHub</strong>: an operator can run a manual restore drill that copies the
              production database to a temporary GitHub Actions runner. The copy stays on the runner
              and is deleted after the drill.
            </li>
            <li>
              <strong>Stripe</strong>: there are no sales today, and payments are in test mode. The
              production API isn&apos;t given a Stripe secret key, so it can&apos;t start a payment
              and sends nothing to Stripe. PatchHive doesn&apos;t ask for payment details.
            </li>
            <li>
              <strong>Outside AI providers</strong>: on production, photos go to none today.
              PatchHive&apos;s code can call NVIDIA, Cloudflare Workers AI and Typesafe, but the
              production API never receives their credentials or the switches that turn them on.
              Only the separate staging site can hold those.
            </li>
          </ul>
        </section>

        <section className="ops-section" aria-labelledby="privacy-browser">
          <h2 id="privacy-browser">Cookies and browser storage</h2>
          <ul className="privacy-list">
            <li>
              PatchHive&apos;s own code sets one cookie, <code>__Host-ph_refresh</code>, on
              api.patch-hive.com when you sign in. It holds a session token for up to 30 days, and
              page scripts can&apos;t read it.
            </li>
            <li>
              Your browser&apos;s local storage holds your theme choice, a hint about whether
              you&apos;re signed in, and any style recipes you save.
            </li>
            <li>The short-lived access token stays in the page&apos;s memory only.</li>
          </ul>
        </section>

        <section className="ops-section" aria-labelledby="privacy-undecided">
          <h2 id="privacy-undecided">Not decided yet</h2>
          <ul className="privacy-list">
            <li>
              How long the rows kept after account deletion stay, and whether the text inside them
              has to go.
            </li>
            <li>How long request logs, reports and admin audit records are kept.</li>
            <li>How backups are treated.</li>
            <li>What happens to any text read from photos.</li>
            <li>
              Whether the 30-day default and 90-day maximum for photos stand. Counsel still has to
              confirm them.
            </li>
            <li>Which region holds the database. This notice doesn&apos;t state one yet.</li>
          </ul>
        </section>

        <section className="ops-section" aria-labelledby="privacy-requests">
          <h2 id="privacy-requests">Privacy requests</h2>
          <div className="privacy-gap">
            <p>
              <strong>Gap: no contact address yet.</strong>
            </p>
            <p>
              PatchHive has no working contact address for privacy requests yet. The address will be
              privacy@patch-hive.com, but that mailbox hasn&apos;t been created, so it can&apos;t
              receive anything today. Until it works, the account page is the only route to deleting
              your data.
            </p>
          </div>
        </section>
      </div>
    </section>
  );
}
