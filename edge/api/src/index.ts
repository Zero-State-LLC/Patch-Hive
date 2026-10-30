// Edge entry for api.patch-hive.com (production) and api-staging.patch-hive.com
// (staging): forwards every request to the FastAPI container.
import { DurableObject } from "cloudflare:workers";

interface Env extends Partial<Record<OptionalName, string>> {
  API: DurableObjectNamespace<PatchHiveApi>;
  DATABASE_URL?: string;
  SECRET_KEY?: string;
  S3_ENDPOINT_URL?: string;
  S3_ACCESS_KEY_ID?: string;
  S3_SECRET_ACCESS_KEY?: string;
  ENVIRONMENT: string;
  FRONTEND_BASE_URL: string;
  CORS_ORIGINS: string;
  STRIPE_TEST_MODE: string;
  ALLOW_PRODUCTION_PAYMENTS: string;
  STORAGE_BACKEND: string;
  S3_BUCKET: string;
  S3_REGION: string;
  S3_KEY_PREFIX: string;
  // Opt-in only. Neither environment sets it in wrangler.jsonc: databases are migrated
  // by the db-migrate workflow, never by a cold start.
  RUN_MIGRATIONS?: string;
}

// Feature flags and decision-provider settings, forwarded only when the Worker sets
// them. Production sets none, and the container never receives them there, so every
// flag stays at its backend default (off); staging sets them for the 007/008 drills.
const FLAG_VARS = [
  "ENABLE_DECISION_INTELLIGENCE",
  "DECISION_PROVIDER",
  "ENABLE_CLEF_PROVIDER",
  "CLEF_MODEL",
  "ENABLE_PATCHBOOK_DESIGN_ENGINE",
  "ENABLE_CANON_EXPORT_FULFILLMENT",
  "ENABLE_INLINE_EXPORT_FULFILLMENT",
  "ENABLE_PATCHBOOK_PUBLICATION_PROFILE",
] as const;

// OptionalName secrets: forwarded in every environment when set.
const OPTIONAL_SECRETS = ["STRIPE_WEBHOOK_SECRET", "DOWNLOAD_TOKEN_SECRET"] as const;

// Provider credentials, which only staging may hold.
const STAGING_SECRETS = ["TYPESAFE_API_KEY", "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_AI_API_TOKEN"] as const;

type OptionalName = (typeof FLAG_VARS)[number] | (typeof OPTIONAL_SECRETS)[number] | (typeof STAGING_SECRETS)[number];

// The names the container receives beyond its fixed set. Exported for tests.
export function optionalEnv(env: Partial<Record<OptionalName, string>> & { ENVIRONMENT: string }): Record<string, string> {
  const names: OptionalName[] = [...OPTIONAL_SECRETS];
  if (env.ENVIRONMENT !== "production") names.push(...FLAG_VARS, ...STAGING_SECRETS);
  const out: Record<string, string> = {};
  for (const name of names) {
    const value = env[name];
    if (value) out[name] = value;
  }
  return out;
}

const REQUIRED_SECRETS = [
  "DATABASE_URL",
  "SECRET_KEY",
  "S3_ENDPOINT_URL",
  "S3_ACCESS_KEY_ID",
  "S3_SECRET_ACCESS_KEY",
] as const;

// Stop the container after this long without a request (it restores durable files
// from R2 on the next start).
const INACTIVITY_TIMEOUT_MS = 15 * 60 * 1000;
// The entrypoint waits for the database (and, only when RUN_MIGRATIONS opts in, runs
// `alembic upgrade head`) before uvicorn listens, so a cold start can take a while.
const READY_ATTEMPTS = 300;
const PORT = 8000;

export class PatchHiveApi extends DurableObject<Env> {
  private starting: Promise<void> | undefined;
  private imageChecked = false;

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    const container = ctx.container!;
    if (container.running) {
      void ctx.blockConcurrencyWhile(() => container.setInactivityTimeout(INACTIVITY_TIMEOUT_MS));
    }
  }

  async fetch(request: Request): Promise<Response> {
    // Concurrent requests share one start and readiness check.
    this.starting ??= this.startAndWaitUntilHealthy().finally(() => {
      this.starting = undefined;
    });
    try {
      await this.starting;
    } catch (error) {
      // Logged so a start failure shows in `wrangler tail` instead of only as a 503.
      console.error("api container start failed", describe(error));
      return Response.json({ status: "unavailable", reason: "api container not ready" }, { status: 503 });
    }
    // Keep the public host so absolute URLs the API builds (trailing-slash redirects,
    // links) point at api.patch-hive.com, not at the container. The hop to the container
    // is plain http, so pass the public scheme and client address as forwarded headers
    // (uvicorn trusts them: FORWARDED_ALLOW_IPS below), overwriting any a client sent.
    const publicUrl = new URL(request.url);
    const forwarded = new Request(request.url.replace(/^https:/, "http:"), request);
    forwarded.headers.set("x-forwarded-proto", publicUrl.protocol.replace(":", ""));
    forwarded.headers.set("x-forwarded-for", request.headers.get("cf-connecting-ip") ?? "");
    return this.ctx.container!.getTcpPort(PORT).fetch(forwarded);
  }

  private async startAndWaitUntilHealthy(): Promise<void> {
    const container = this.ctx.container!;
    // Under the durable_object policy a deploy does not roll the running container.
    // A deploy does restart this Durable Object, so the first request after one checks
    // the running image and replaces the container when the deploy brought a new one.
    // The same goes for its environment (vars and secrets), so the container carries a
    // hash of the environment it started with and is replaced when that changes too.
    const env = containerEnv(this.env);
    const envHash = await sha256(JSON.stringify(Object.entries(env).sort()));
    if (container.running && !this.imageChecked) {
      const info = await container.inspect();
      const stale =
        info !== null &&
        (imageDigest(info.image) !== imageDigest(container.images.api) || info.labels[ENV_LABEL] !== envHash);
      if (stale) {
        await container.destroy();
      }
    }
    this.imageChecked = true;
    if (!container.running) {
      container.start({
        image: container.images.api,
        instance: "standard-1",
        // The container reaches Neon directly over TLS. Hyperdrive serves only Worker
        // runtime clients, not a Postgres driver inside a container.
        enableInternet: true,
        env,
        labels: { [ENV_LABEL]: envHash },
      });
    }
    await container.setInactivityTimeout(INACTIVITY_TIMEOUT_MS);

    const port = container.getTcpPort(PORT);
    let lastError: unknown;
    for (let attempt = 0; attempt < READY_ATTEMPTS; attempt++) {
      try {
        const response = await port.fetch("http://container/health", { signal: AbortSignal.timeout(1000) });
        await response.body?.cancel();
        if (response.ok) return;
        lastError = new Error(`health returned ${response.status}`);
      } catch (error) {
        lastError = error;
      }
      await scheduler.wait(500);
    }
    throw new Error("api container did not become healthy", { cause: lastError });
  }
}

// Cloudflare caps container label names at 16 bytes.
const ENV_LABEL = "ph-env-sha256";

function describe(error: unknown): string {
  if (!(error instanceof Error)) return String(error);
  return error.cause ? `${error.name}: ${error.message} (cause: ${String(error.cause)})` : `${error.name}: ${error.message}`;
}

async function sha256(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// Compare images by digest when both references carry one (tags and registry
// prefixes can be spelled differently for the same image).
function imageDigest(ref: string): string {
  return /sha256:[0-9a-f]{64}/.exec(ref)?.[0] ?? ref;
}

// Only the exact values "true" and "1" enable startup migrations; anything else,
// including unset, sends "false". Exported for tests.
export function runMigrations(value: string | undefined): "true" | "false" {
  return value === "true" || value === "1" ? "true" : "false";
}

function containerEnv(env: Env): Record<string, string> {
  return {
    DATABASE_URL: env.DATABASE_URL ?? "",
    SECRET_KEY: env.SECRET_KEY ?? "",
    ENVIRONMENT: env.ENVIRONMENT,
    FRONTEND_BASE_URL: env.FRONTEND_BASE_URL,
    CORS_ORIGINS: env.CORS_ORIGINS,
    STRIPE_TEST_MODE: env.STRIPE_TEST_MODE,
    ALLOW_PRODUCTION_PAYMENTS: env.ALLOW_PRODUCTION_PAYMENTS,
    STORAGE_BACKEND: env.STORAGE_BACKEND,
    S3_ENDPOINT_URL: env.S3_ENDPOINT_URL ?? "",
    S3_BUCKET: env.S3_BUCKET,
    S3_ACCESS_KEY_ID: env.S3_ACCESS_KEY_ID ?? "",
    S3_SECRET_ACCESS_KEY: env.S3_SECRET_ACCESS_KEY ?? "",
    S3_REGION: env.S3_REGION,
    S3_KEY_PREFIX: env.S3_KEY_PREFIX,
    // Cold starts never migrate unless the Worker explicitly opts in.
    RUN_MIGRATIONS: runMigrations(env.RUN_MIGRATIONS),
    // Only the Worker can reach the container, so trust its forwarded headers.
    FORWARDED_ALLOW_IPS: "*",
    ...optionalEnv(env),
  };
}

// Headers every API response carries: HTTPS only, no MIME sniffing, never framed.
export const API_SECURITY_HEADERS: Record<string, string> = {
  "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "strict-origin-when-cross-origin",
};

export function withSecurityHeaders(response: Response): Response {
  const secured = new Response(response.body, response);
  for (const [name, value] of Object.entries(API_SECURITY_HEADERS)) {
    secured.headers.set(name, value);
  }
  return secured;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // Fail closed: without these the backend would boot on its development defaults.
    const missing = REQUIRED_SECRETS.filter((name) => !env[name]);
    if (missing.length > 0) {
      return withSecurityHeaders(
        Response.json(
          { status: "unavailable", reason: "api secrets not configured", missing },
          { status: 503 },
        ),
      );
    }
    return withSecurityHeaders(await env.API.getByName("primary").fetch(request));
  },
};
