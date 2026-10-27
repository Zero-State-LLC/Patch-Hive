// Edge entry for api.patch-hive.com: forwards every request to the FastAPI container.
import { Container, getContainer } from "@cloudflare/containers";

interface Env {
  API: DurableObjectNamespace<PatchHiveApi>;
  DATABASE_URL?: string;
  SECRET_KEY?: string;
  ENVIRONMENT: string;
  FRONTEND_BASE_URL: string;
  CORS_ORIGINS: string;
  STRIPE_TEST_MODE: string;
  ALLOW_PRODUCTION_PAYMENTS: string;
}

const REQUIRED_SECRETS = ["DATABASE_URL", "SECRET_KEY"] as const;

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
