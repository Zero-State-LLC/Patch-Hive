import assert from "node:assert/strict";
import test from "node:test";
import { evaluateAuditReport } from "./audit-policy.mjs";

test("accepts only the documented React Router advisory and its wrapper", () => {
  const result = evaluateAuditReport({
    vulnerabilities: {
      "react-router": {
        name: "react-router",
        via: [{ url: "https://github.com/advisories/GHSA-qwww-vcr4-c8h2" }],
      },
      "react-router-dom": { name: "react-router-dom", via: ["react-router"] },
    },
  });

  assert.equal(result.directAdvisories.length, 1);
  assert.deepEqual(result.unexpectedAdvisories, []);
  assert.deepEqual(result.unexpectedWrappers, []);
});

test("rejects every new advisory", () => {
  const result = evaluateAuditReport({
    vulnerabilities: {
      example: {
        name: "example",
        via: [{ url: "https://github.com/advisories/GHSA-new-finding" }],
      },
    },
  });

  assert.equal(result.unexpectedAdvisories.length, 1);
});

test("rejects unresolved wrapper findings", () => {
  const result = evaluateAuditReport({
    vulnerabilities: {
      wrapper: { name: "wrapper", via: ["missing-dependency"] },
    },
  });

  assert.equal(result.unexpectedWrappers.length, 1);
});
