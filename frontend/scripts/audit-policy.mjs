export const allowedAdvisories = new Set([
  // React Router RSC server-action CSRF. PatchHive is BrowserRouter-only and has no RSC runtime.
  "https://github.com/advisories/GHSA-qwww-vcr4-c8h2",
]);

export function evaluateAuditReport(report) {
  const vulnerabilities = Object.values(report.vulnerabilities || {});
  const directAdvisories = vulnerabilities.flatMap((vulnerability) =>
    vulnerability.via.filter((entry) => typeof entry === "object"),
  );
  const unexpectedAdvisories = directAdvisories.filter(
    (advisory) => !allowedAdvisories.has(advisory.url),
  );
  const unexpectedWrappers = vulnerabilities.filter((vulnerability) =>
    vulnerability.via.some(
      (entry) => typeof entry === "string" && !report.vulnerabilities?.[entry],
    ),
  );

  return { directAdvisories, unexpectedAdvisories, unexpectedWrappers };
}
