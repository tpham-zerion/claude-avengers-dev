# Tracker data reference

The page reads four kinds of document from the artifact's database. It writes
nothing. Every field is optional unless marked required; the page shows a sensible
empty state for anything missing.

All timestamps are ISO 8601 UTC from `date -u +%Y-%m-%dT%H:%M:%SZ` (or a PR's
`mergedAt` for a done item). The page shows them in the viewer's local time.

## `meta/config`

Names the page and sets the link base.

| Field | Type | Meaning |
| ----- | ---- | ------- |
| `title` | string | Page heading and browser title. Default: "Progress Tracker". |
| `subtitle` | string | Line under the heading. Hidden when empty. |
| `repoUrl` | string | `http(s)` repo URL. Issue links go to `{repoUrl}/issues/{n}`, PR links to `{repoUrl}/pull/{n}`. Absent or not `http(s)`: plain `#N` text, no links. |

```json
{
  "title": "Billing Service Rewrite",
  "subtitle": "Invoices and payments, monolith to service",
  "repoUrl": "https://github.com/example-org/billing-service"
}
```

## `items/<id>`

One doc per work item, shown as a card on the board.

| Field | Type | Meaning |
| ----- | ---- | ------- |
| `title` | string | Card heading. Default "Untitled". |
| `area` | string | Filter group. Exact string match: spell it the same everywhere. |
| `status` | `active` \| `queued` \| `backlog` \| `done` | Column: In progress, Up next, Backlog, Done. |
| `issue` | number | Issue number, linked when `repoUrl` is set. |
| `pr` | number | PR number, linked when `repoUrl` is set. |
| `note` | string | Plain text under the title; line breaks kept. |
| `order` | number | Sort order in every column but Done (lower first; unset sorts last). |
| `flag` | `security` \| `decision` \| `drift` | Chip on the card; open flagged items count in the Security and "Parked sign-offs" tiles (parked, never blocking). |
| `updatedAt` | ISO string | Shown on the card. Done sorts newest first by it. |

```json
{
  "title": "Rate limit on sign-in",
  "area": "Auth",
  "status": "done",
  "issue": 142,
  "pr": 157,
  "note": "Five attempts per minute per account.\nMatches the old behaviour.",
  "order": 3,
  "flag": "security",
  "updatedAt": "2026-11-12T16:04:51Z"
}
```

## `meta/status`

The left pane's Working on and Next, the header's "Updated" time, and the activity
log.

| Field | Type | Meaning |
| ----- | ---- | ------- |
| `current` | string | Working on. |
| `next` | string | Next. |
| `updatedAt` | ISO string | Header "Updated" time. |
| `log` | array of `{at, text}` | Recent activity, newest first. The page shows the first 40; keep at most ~40. |

```json
{
  "current": "Invoice PDF export (#151)",
  "next": "Refund webhooks (#160)",
  "updatedAt": "2026-11-12T16:05:10Z",
  "log": [
    { "at": "2026-11-12T16:05:10Z", "text": "Merged PR #157: rate limit on sign-in." },
    { "at": "2026-11-12T09:41:27Z", "text": "Started invoice PDF export." }
  ]
}
```

## `meta/progress`

The centre progress panel and the left pane's milestones. Absent: both stay hidden.

| Field | Type | Meaning |
| ----- | ---- | ------- |
| `measuredAt` | ISO string | When the count ran. |
| `basis` | string | What was counted, in one sentence. |
| `unit` | string | Headline reads "`{pct}% of {unit} (done of total)`"; absent: "`{pct}% complete`". |
| `areas` | array of `{name, done, total}` | Required for the panel to show. One meter each; the headline sums them. |
| `components` | array of `{name, status}` | Chips under the meters. `status`: `done` \| `active` \| `todo`. |
| `milestones` | array of `{n, title, issue, status}` | Left-pane list, linked to `issue`. `status`: `done` \| `active` \| `todo`, from the code, not the issue state. |

```json
{
  "measuredAt": "2026-11-12T15:58:02Z",
  "basis": "Stories in the billing epic, closed with merged work, counted with gh issue list.",
  "unit": "stories done",
  "areas": [
    { "name": "Auth", "done": 4, "total": 6 },
    { "name": "Invoices", "done": 2, "total": 9 }
  ],
  "components": [
    { "name": "API", "status": "active" },
    { "name": "Worker", "status": "todo" }
  ],
  "milestones": [
    { "n": 1, "title": "Sign-in parity", "issue": 140, "status": "done" },
    { "n": 2, "title": "Invoice export", "issue": 150, "status": "active" }
  ]
}
```
