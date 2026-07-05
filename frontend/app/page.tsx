type HealthResult =
  | {
      ok: true;
      endpoint: string;
      data: unknown;
    }
  | {
      ok: false;
      endpoints: string[];
      message: string;
    };

export const dynamic = "force-dynamic";

function normalizeBaseUrl(url: string): string {
  return url.replace(/\/$/, "");
}

function getApiBaseUrls(): string[] {
  const publicBaseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";
  const urls = [
    process.env.BACKEND_INTERNAL_URL || publicBaseUrl,
    publicBaseUrl
  ];

  return Array.from(new Set(urls.map(normalizeBaseUrl)));
}

async function getBackendHealth(): Promise<HealthResult> {
  const endpoints = getApiBaseUrls().map((baseUrl) => `${baseUrl}/health`);

  for (const endpoint of endpoints) {
    try {
      const response = await fetch(endpoint, {
        cache: "no-store",
        signal: AbortSignal.timeout(3000)
      });

      if (!response.ok) {
        continue;
      }

      return {
        ok: true,
        endpoint,
        data: await response.json()
      };
    } catch {
      continue;
    }
  }

  return {
    ok: false,
    endpoints,
    message: "Backend health check did not return a successful response."
  };
}

export default async function Home() {
  const health = await getBackendHealth();

  return (
    <main className="min-h-screen px-6 py-10 sm:px-10">
      <section className="mx-auto max-w-3xl">
        <p className="text-sm font-medium uppercase tracking-wide text-slate-500">
          Sourcewise
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">
          Minimal frontend health check
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-slate-700">
          This placeholder Next.js app only verifies that the frontend can run
          and reach the backend health endpoint.
        </p>

        <div className="mt-8 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-lg font-medium text-slate-950">
              Backend health
            </h2>
            <span
              className={
                health.ok
                  ? "inline-flex w-fit rounded-full bg-emerald-50 px-3 py-1 text-sm font-medium text-emerald-700"
                  : "inline-flex w-fit rounded-full bg-amber-50 px-3 py-1 text-sm font-medium text-amber-700"
              }
            >
              {health.ok ? "Connected" : "Unavailable"}
            </span>
          </div>

          {health.ok ? (
            <p className="mt-4 break-all text-sm text-slate-600">
              Endpoint: {health.endpoint}
            </p>
          ) : (
            <div className="mt-4 text-sm text-slate-600">
              <p>Endpoints attempted:</p>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {health.endpoints.map((endpoint) => (
                  <li className="break-all" key={endpoint}>
                    {endpoint}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {health.ok ? (
            <pre className="mt-4 overflow-x-auto rounded-md bg-slate-950 p-4 text-sm text-slate-50">
              {JSON.stringify(health.data, null, 2)}
            </pre>
          ) : (
            <p className="mt-4 rounded-md bg-amber-50 p-4 text-sm text-amber-900">
              {health.message} Start the backend API and reload this page.
            </p>
          )}
        </div>
      </section>
    </main>
  );
}
