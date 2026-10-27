// Edge entry for api.patch-hive.com: forwards every request to the FastAPI container.
import { Container, getContainer } from "@cloudflare/containers";

interface Env {
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

const REQUIRED_SECRETS = [
  "DATABASE_URL",
  "SECRET_KEY",
  "S3_ENDPOINT_URL",
  "S3_ACCESS_KEY_ID",
  "S3_SECRET_ACCESS_KEY",
] as const;

export class PatchHiveApi extends Container<Env> {
  defaultPort = 8000;
  sleepAfter = "15m";
  // The container reaches Neon directly over TLS. Hyperdrive serves only Worker
  // runtime clients, not a Postgres driver inside a container.
  enableInternet = true;

  constructor(ctx: DurableObjectState<{}>, env: Env) {
    super(ctx, env);
    this.envVars = {
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
    };
  }
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
    return getContainer(env.API, "primary").fetch(request);
  },
};
