import { spawnSync } from "node:child_process";
import { evaluateAuditReport } from "./audit-policy.mjs";

const result = spawnSync("npm", ["audit", "--json"], {
  cwd: new URL("..", import.meta.url),
  encoding: "utf8",
  shell: process.platform === "win32",
});

if (!result.stdout) {
  process.stderr.write(result.stderr || "npm audit produced no JSON output\n");
  process.exit(1);
}

let report;
try {
  report = JSON.parse(result.stdout);
} catch (error) {
  process.stderr.write(`Unable to parse npm audit output: ${error}\n`);
  process.exit(1);
}

const { directAdvisories, unexpectedAdvisories, unexpectedWrappers } = evaluateAuditReport(report);

if (unexpectedAdvisories.length || unexpectedWrappers.length) {
  process.stderr.write("Unexpected npm audit findings:\n");
  for (const advisory of unexpectedAdvisories) {
    process.stderr.write(`- ${advisory.severity}: ${advisory.title} (${advisory.url})\n`);
  }
  for (const wrapper of unexpectedWrappers) {
    process.stderr.write(`- unresolved dependency finding: ${wrapper.name}\n`);
  }
  process.exit(1);
}

if (directAdvisories.length === 0 && result.status !== 0) {
  process.stderr.write(result.stderr || "npm audit failed without a recognized advisory\n");
  process.exit(1);
}

if (directAdvisories.length > 0) {
  process.stdout.write(
    `Accepted ${directAdvisories.length} documented, unreachable advisory; no unexpected findings.\n`,
  );
} else {
  process.stdout.write("No known npm vulnerabilities found.\n");
}
