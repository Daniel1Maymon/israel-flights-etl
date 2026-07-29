import { Fragment, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { API_ENDPOINTS } from "@/config/api";

const TOKEN_KEY = "rankair_admin_token";

type Metrics = {
  total_questions: number;
  unique_users: number;
  unique_ips: number;
  total_tokens: number;
  estimated_cost_usd: number;
  refusal_rate: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  questions_per_day: { day: string; count: number }[];
  refusals_by_reason: { reason: string; count: number }[];
  top_countries: { country: string; country_code: string | null; count: number }[];
};

type EventRow = {
  created_at: string;
  question: string;
  answer: string | null;
  refused: boolean;
  reason: string | null;
  tokens: number;
  latency_ms: number | null;
  handler: string | null;
  row_count: number | null;
  country: string | null;
  country_code: string | null;
  ip: string | null;
  ip_questions_today: number | null;
};

type LLMFlag = {
  enabled: boolean;
  updated_at: string | null;
  note: string | null;
};

class AuthError extends Error {}

async function authedGet<T>(url: string, token: string): Promise<T> {
  const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (res.status === 401) throw new AuthError("unauthorized");
  if (!res.ok) throw new Error(`request failed: ${res.status}`);
  return res.json() as Promise<T>;
}

async function authedPost<T>(url: string, token: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.status === 401) throw new AuthError("unauthorized");
  if (!res.ok) throw new Error(`request failed: ${res.status}`);
  return res.json() as Promise<T>;
}

function flag(cc: string | null): string {
  if (!cc || cc.length !== 2) return "";
  return String.fromCodePoint(
    ...[...cc.toUpperCase()].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65)
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold tabular-nums">{value}</div>
      </CardContent>
    </Card>
  );
}

/**
 * Bar colour for a refusal reason — the two that need someone to act stand out from the rest.
 *
 * Red is a fault. Amber is a ceiling we hit: `provider_quota` means the provider stopped serving
 * us (a spend cap, a quota, a rate limit) and `budget` means our own monthly ceiling tripped.
 * Both stop AI search dead while nothing is wrong with the data, and neither clears itself
 * without someone raising a limit — so seeing them at a glance is the point.
 */
function refusalColor(reason: string): string {
  if (reason === "error") return "#ef4444";
  if (reason === "provider_quota" || reason === "budget") return "#f59e0b";
  return "hsl(var(--primary))";
}

/**
 * The AI kill switch.
 *
 * Green = AI search is answering questions. Red = every question is refused before an LLM is
 * called, with a message saying the feature is off; the rest of the site is unaffected.
 *
 * The colour is read from the server on every load, never from local state: flip it here and the
 * same dashboard opened on another device must show red too. The DB row is the only truth.
 */
function LLMSwitch({ token }: { token: string }) {
  const queryClient = useQueryClient();

  const flagQ = useQuery({
    queryKey: ["admin-llm", token],
    queryFn: () => authedGet<LLMFlag>(API_ENDPOINTS.ADMIN_LLM, token),
    retry: false,
    refetchInterval: 30_000,
  });

  const setFlag = useMutation({
    // Sends the state it wants, never "flip": two dashboards open, or one double-click, would
    // otherwise race on read-then-invert and land on whichever request lost.
    mutationFn: (enabled: boolean) =>
      authedPost<LLMFlag>(API_ENDPOINTS.ADMIN_LLM, token, { enabled }),
    onSuccess: (data) => queryClient.setQueryData(["admin-llm", token], data),
  });

  const enabled = flagQ.data?.enabled;
  const busy = flagQ.isLoading || setFlag.isPending;

  const onClick = () => {
    if (enabled === undefined) return;
    // Turning it off takes the feature away from every visitor at once. A misclick on the way to
    // the events table should not be able to do that silently.
    if (enabled && !window.confirm("Turn AI search OFF for all users?")) return;
    setFlag.mutate(!enabled);
  };

  return (
    <Card>
      <CardContent className="flex flex-wrap items-center justify-between gap-4 py-4">
        <div>
          <div className="font-medium">AI search</div>
          <div className="text-sm text-muted-foreground">
            {enabled === undefined
              ? "Reading state…"
              : enabled
                ? "Answering questions — LLM calls are being made."
                : "Off — every question is refused before any LLM call. No tokens are spent."}
          </div>
          {flagQ.data?.updated_at && (
            <div className="text-xs text-muted-foreground mt-1">
              Last changed {flagQ.data.updated_at}
              {flagQ.data.note ? ` · ${flagQ.data.note}` : ""}
            </div>
          )}
          {setFlag.isError && (
            <div className="text-xs text-red-500 mt-1">Could not change it. Try again.</div>
          )}
        </div>

        <button
          onClick={onClick}
          disabled={busy || enabled === undefined}
          aria-pressed={!!enabled}
          className={`shrink-0 rounded-md px-4 py-2 text-sm font-semibold text-white transition-opacity disabled:opacity-50 ${
            enabled ? "bg-green-600 hover:bg-green-700" : "bg-red-600 hover:bg-red-700"
          }`}
        >
          {busy ? "Working…" : enabled ? "ON — click to turn off" : "OFF — click to turn on"}
        </button>
      </CardContent>
    </Card>
  );
}

function TokenGate({ onSubmit, error }: { onSubmit: (t: string) => void; error?: string }) {
  const [value, setValue] = useState("");
  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4" dir="ltr">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Admin dashboard</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (value.trim()) onSubmit(value.trim());
            }}
            className="space-y-3"
          >
            <input
              type="password"
              autoFocus
              placeholder="Admin token"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
            />
            {error && <p className="text-sm text-red-500">{error}</p>}
            <button
              type="submit"
              className="w-full rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
            >
              Enter
            </button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

export default function Admin() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const metricsQ = useQuery({
    queryKey: ["admin-metrics", token],
    queryFn: () => authedGet<Metrics>(API_ENDPOINTS.ADMIN_METRICS, token!),
    enabled: !!token,
    retry: false,
    refetchInterval: 30_000,
  });

  const eventsQ = useQuery({
    queryKey: ["admin-events", token],
    queryFn: () => authedGet<{ events: EventRow[] }>(`${API_ENDPOINTS.ADMIN_EVENTS}?limit=200`, token!),
    enabled: !!token,
    retry: false,
    refetchInterval: 30_000,
  });

  const authFailed = metricsQ.error instanceof AuthError || eventsQ.error instanceof AuthError;

  const saveToken = (t: string) => {
    localStorage.setItem(TOKEN_KEY, t);
    setToken(t);
  };
  const clearToken = () => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
  };
  const toggleRow = (i: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });
  };

  if (!token || authFailed) {
    return <TokenGate onSubmit={saveToken} error={authFailed ? "Invalid token." : undefined} />;
  }

  const m = metricsQ.data;
  const events = eventsQ.data?.events ?? [];

  return (
    <div className="min-h-screen bg-background text-foreground p-6" dir="ltr">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">AI Search — Analytics</h1>
          <button
            onClick={clearToken}
            className="text-sm text-muted-foreground hover:text-foreground underline"
          >
            Log out
          </button>
        </div>

        <LLMSwitch token={token} />

        {metricsQ.isLoading && <p className="text-muted-foreground">Loading…</p>}

        {m && (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard label="Total questions" value={m.total_questions.toLocaleString()} />
              {/* Counted by IP. "Unique users" was one-per-question until the cookie identity was
              replaced, so rows from before the ip column still inflate the headline number —
              hence the separate, trustworthy count beside it. */}
          <StatCard
            label="Unique visitors (by IP)"
            value={`${m.unique_ips.toLocaleString()}${
              m.unique_users > m.unique_ips ? ` / ${m.unique_users.toLocaleString()} legacy` : ""
            }`}
          />
              <StatCard label="Refusal rate" value={`${(m.refusal_rate * 100).toFixed(1)}%`} />
              <StatCard label="Est. cost" value={`$${m.estimated_cost_usd.toFixed(2)}`} />
              <StatCard label="Total tokens" value={m.total_tokens.toLocaleString()} />
              <StatCard label="Latency p50" value={`${m.p50_latency_ms} ms`} />
              <StatCard label="Latency p95" value={`${m.p95_latency_ms} ms`} />
            </div>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Questions per day (30d)</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={m.questions_per_day}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                    <XAxis dataKey="day" fontSize={11} tickMargin={8} minTickGap={24} />
                    <YAxis fontSize={11} allowDecimals={false} width={32} />
                    <Tooltip />
                    <Line
                      type="monotone"
                      dataKey="count"
                      stroke="hsl(var(--primary))"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Refusals by reason</CardTitle>
                </CardHeader>
                <CardContent>
                  {m.refusals_by_reason.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No refusals yet.</p>
                  ) : (
                    <ResponsiveContainer width="100%" height={260}>
                      <BarChart data={m.refusals_by_reason}>
                        <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                        <XAxis dataKey="reason" fontSize={11} tickMargin={8} />
                        <YAxis fontSize={11} allowDecimals={false} width={32} />
                        <Tooltip />
                        <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                          {m.refusals_by_reason.map((entry) => (
                            <Cell key={entry.reason} fill={refusalColor(entry.reason)} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Top countries</CardTitle>
                </CardHeader>
                <CardContent>
                  {m.top_countries.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No geo data yet.</p>
                  ) : (
                    <ul className="space-y-2">
                      {m.top_countries.map((c) => (
                        <li key={c.country} className="flex items-center justify-between text-sm">
                          <span>
                            {flag(c.country_code)} {c.country}
                          </span>
                          <span className="tabular-nums text-muted-foreground">{c.count}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </CardContent>
              </Card>
            </div>
          </>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent questions ({events.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-muted-foreground border-b">
                  <tr>
                    <th className="py-2 pr-4 font-medium whitespace-nowrap">Time</th>
                    <th className="py-2 pr-4 font-medium">Question</th>
                    <th className="py-2 pr-4 font-medium whitespace-nowrap">Country</th>
                    <th className="py-2 pr-4 font-medium whitespace-nowrap">IP</th>
                    <th className="py-2 pr-4 font-medium">Status</th>
                    <th className="py-2 pr-4 font-medium whitespace-nowrap">Latency</th>
                    <th className="py-2 pr-4 font-medium whitespace-nowrap">Tokens</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((e, i) => (
                    <Fragment key={i}>
                      <tr
                        className="border-b last:border-0 align-top cursor-pointer hover:bg-muted/40"
                        onClick={() => toggleRow(i)}
                      >
                        <td className="py-2 pr-4 whitespace-nowrap text-muted-foreground tabular-nums">
                          {e.created_at}
                        </td>
                        <td className="py-2 pr-4 max-w-md" dir="auto">
                          <span className="text-muted-foreground mr-1">
                            {expanded.has(i) ? "▾" : "▸"}
                          </span>
                          {e.question}
                        </td>
                        <td className="py-2 pr-4 whitespace-nowrap">
                          {e.country_code ? `${flag(e.country_code)} ${e.country_code}` : "—"}
                        </td>
                        {/* The IP is what the daily cap counts, so the count beside it says how far
                            through the quota this visitor is — the number to look at when asking
                            whether the cap is working. */}
                        <td className="py-2 pr-4 whitespace-nowrap font-mono text-xs" dir="ltr">
                          {e.ip ? (
                            <>
                              {e.ip}
                              {e.ip_questions_today != null && (
                                <span
                                  className={`ml-2 tabular-nums ${
                                    e.ip_questions_today >= 10
                                      ? "text-red-500"
                                      : "text-muted-foreground"
                                  }`}
                                  title="questions from this IP that day"
                                >
                                  ×{e.ip_questions_today}
                                </span>
                              )}
                            </>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </td>
                        <td className="py-2 pr-4 whitespace-nowrap">
                          {e.refused ? (
                            <span className="text-red-500">refused · {e.reason ?? "—"}</span>
                          ) : (
                            <span className="text-green-600">
                              answered{e.handler ? ` · ${e.handler}` : ""}
                            </span>
                          )}
                        </td>
                        <td className="py-2 pr-4 whitespace-nowrap tabular-nums text-muted-foreground">
                          {e.latency_ms != null ? `${e.latency_ms} ms` : "—"}
                        </td>
                        <td className="py-2 pr-4 whitespace-nowrap tabular-nums text-muted-foreground">
                          {e.tokens}
                        </td>
                      </tr>
                      {expanded.has(i) && (
                        <tr className="border-b last:border-0 bg-muted/30">
                          <td colSpan={7} className="py-3 px-4" dir="auto">
                            <div className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
                              Answer shown to user
                            </div>
                            {e.answer ? (
                              <div className="whitespace-pre-wrap leading-relaxed">{e.answer}</div>
                            ) : (
                              <div className="text-muted-foreground">
                                (no answer — {e.refused ? `refused: ${e.reason ?? "—"}` : "empty"})
                              </div>
                            )}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                  {events.length === 0 && !eventsQ.isLoading && (
                    <tr>
                      <td colSpan={6} className="py-6 text-center text-muted-foreground">
                        No questions recorded yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
