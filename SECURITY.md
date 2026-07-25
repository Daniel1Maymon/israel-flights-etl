# Security Policy

Thanks for taking the time to look. This project is maintained by one person in their
own time, and reports are genuinely welcome.

## Reporting a vulnerability

**Please do not open a public issue, PR, or discussion for a security problem.**
A public report tells everyone about the weakness before there is a fix.

Two private channels, in order of preference:

1. **GitHub private vulnerability reporting** — go to the
   [Security tab](https://github.com/Daniel1Maymon/israel-flights-etl/security/advisories/new)
   and choose *Report a vulnerability*. This keeps the whole thread private until a fix
   ships and is the easiest way to stay in the loop.
2. **Email** — daniel1maymon@gmail.com, with `SECURITY` in the subject line.

### What helps

- What you did, in enough detail to reproduce it — a `curl` command is ideal
- What you got back versus what you expected
- Why you think it matters (data exposure, availability, integrity)
- Whether you have already told anyone else

You do not need a working exploit. A clear description of the weakness is plenty.

### What to expect

| Stage | Target |
|---|---|
| Acknowledgement that a human read it | within 5 days |
| Initial assessment (valid / not / need more info) | within 14 days |
| Fix for a confirmed high-severity issue | as fast as reasonably possible |

These are targets from a solo maintainer, not an SLA. If you have not heard back in two
weeks, please send a follow-up — it means the message was missed, not ignored.

Credit will be given in the release notes and here unless you prefer to stay anonymous.

## Scope

**In scope**

- The deployed API (Railway backend) and web frontend (Vercel)
- Anything in this repository: backend, ETL, Airflow DAGs, infrastructure config
- The AI search feature, including prompt injection that leads to data or schema
  disclosure, or to queries that were meant to be blocked

**Out of scope**

- Volumetric denial of service (just flooding the service with traffic). Reports about
  *specific requests* that are disproportionately expensive to serve are very much in
  scope.
- Findings from automated scanners with no demonstrated impact
- Social engineering, physical access, or attacks on third-party providers
  (Railway, Vercel, AWS, Google) — report those to the provider
- Missing hardening headers with no exploitable consequence

## Things that are intentional, not bugs

This saves us both time:

- **The flight data itself is public.** It is scraped from the Israel Airports Authority's
  own public feed. "I can read all the flight records" is not a confidentiality issue.
  Reports about *cost* to serve that data, or about anything beyond flight records, are
  still welcome.
- **Read endpoints require no authentication.** This is a public data dashboard; that is
  by design.
- **CORS is restricted to the frontend origin.** This is not, and is not intended as, a
  defence against non-browser clients. CORS is enforced by browsers only.
- **Admin endpoints (`/api/v1/admin/*`) are token-gated and fail closed.** If the token
  is unset, every request is rejected. Their existence is public knowledge.

## Safe harbour

If you make a good-faith effort to follow this policy, I will not pursue or support any
legal action against you for your research. Please:

- Only test against your own data, and stop at proof of concept
- Do not access, modify, or delete data belonging to anyone else
- Do not degrade the service for other users — no load testing, no automated
  high-volume scanning against the live deployment
- Give a reasonable window to fix before publishing

If you are unsure whether something is in bounds, ask first.

## Secrets

Credentials are supplied through environment variables and are never committed. `.env`
files are gitignored. If you believe you have found a live credential in this repository
or its history, please treat it as a high-severity report and use a private channel above.
