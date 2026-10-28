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
// The entrypoint runs `alembic upgrade head` before uvicorn listens, so a cold start
// can take a while.
const READY_ATTEMPTS = 300;
const PORT = 8000;

export class PatchHiveApi extends DurableObject<Env> {
  private starting: Promise<void> | undefined;

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
    } catch {
      return Response.json({ status: "unavailable", reason: "api container not ready" }, { status: 503 });
    }
    const url = new URL(request.url);
    url.protocol = "http:";
    url.host = "container";
    const forwarded = new Request(url, request);
    forwarded.headers.delete("host");
    return this.ctx.container!.getTcpPort(PORT).fetch(forwarded);
  }

  private async startAndWaitUntilHealthy(): Promise<void> {
    const container = this.ctx.container!;
    if (!container.running) {
      container.start({
        image: container.images.api,
        instance: "standard-1",
        // The container reaches Neon directly over TLS. Hyperdrive serves only Worker
        // runtime clients, not a Postgres driver inside a container.
        enableInternet: true,
        env: containerEnv(this.env),
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
    RUN_MIGRATIONS: "true",
    ...optionalEnv(env),
  };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // Fail closed: without these the backend would boot on its development defaults.
    const missing = REQUIRED_SECRETS.filter((name) => !env[name]);
    if (missing.length > 0) {
      return Response.json(
        { status: "unavailable", reason: "api secrets not configured", missing },
        { status: 503 },
      );
    }
    return env.API.getByName("primary").fetch(request);
  },
};
