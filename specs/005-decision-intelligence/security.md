# Security, privacy, governance

- Treat every model/provider response as untrusted input.
- Validate bounded choices against server-authored candidate IDs.
- Never place API keys in requests, packets, logs, fixtures, or committed config.
- Send normalized evidence rather than raw images when the decision provider does not require image bytes.
- Apply provider timeouts, retry caps, payload-size limits, and rate limits.
- Hash retained raw provider payloads; retain full payload only when justified by debugging/privacy policy.
- Prevent prompt/evidence text from changing the allowed answer set or policy.
- Do not log user-sensitive image contents in structured telemetry.
- Feature flag Jev separately from the provider-neutral decision framework.
- A compromised/unavailable provider must be unable to write canon.
