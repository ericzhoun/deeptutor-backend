"""DeepTutor course backend — FastAPI (ASGI) for Vercel.

A serverless slice of the DeepTutor idea (HKUDS/DeepTutor): RAG-grounded
tutoring, quiz generation, and concept explanation over the Backend System
Design course. The full DeepTutor app (PocketBase, WebSockets, FAISS, agent
sandbox) needs a long-running host — see README for the Docker path.
"""
import json
import os
import re
from typing import Optional

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

# --- inlined knowledge base (Vercel bundles only the entry file) ---
"""Course knowledge base for the DeepTutor course backend.

Chunks course.md into module-scoped sections and retrieves by keyword overlap.
Deliberately serverless-safe: no vector store, no on-disk state — everything is
parsed once per cold start from the bundled course file.
"""
import re

_STOP = set("""a an and are as at be by for from how i in is it its of on or that the this to what when which who why with you your do does can""".split())

_HEAD_MOD = re.compile(r"^####\s+(M\d{2})\s*[·\.]\s*(.+?)\s*$")
_HEAD_PART = re.compile(r"^###\s+(Part\s+[IVX]+.*)$")
_HEAD_SEC = re.compile(r"^##\s+(\d\..*|Appendix.*)$")


class CourseKB:
    def __init__(self, text):
        self.chunks = []
        self._parse(text)

    def _parse(self, text):
        part, module, title, buf = "", "", "", []

        def flush():
            body = "\n".join(buf).strip()
            if not body:
                return
            self.chunks.append({
                "module": module or "GEN",
                "title": (title or part or "Course overview")[:90],
                "text": body[:4500],
            })

        for line in text.splitlines():
            m = _HEAD_MOD.match(line)
            p = _HEAD_PART.match(line)
            s = _HEAD_SEC.match(line)
            if m:
                flush()
                buf = []
                module, title = m.group(1), m.group(2)
            elif p:
                flush()
                buf = [line]
                part, module, title = p.group(1), "", p.group(1)
            elif s:
                flush()
                buf = [line]
                module, title = "GEN", s.group(1)
            else:
                if line.strip().startswith("#") or line.strip() == "---":
                    continue
                buf.append(line)
        flush()

    @property
    def modules(self):
        seen = []
        for c in self.chunks:
            if c["module"].startswith("M") and (not seen or seen[-1][0] != c["module"]):
                seen.append((c["module"], c["title"]))
        return [{"module": m, "title": t} for m, t in seen]

    def retrieve(self, query, module=None, k=4):
        terms = [t for t in re.split(r"[^a-z0-9]+", query.lower()) if len(t) > 2 and t not in _STOP]
        scored = []
        for c in self.chunks:
            text = c["text"].lower()
            title = c["title"].lower()
            score = sum(3 if t in title else 0 for t in terms)
            score += sum(1 for t in terms if t in text)
            if module and c["module"] == module:
                score += 6
            if score > 0:
                scored.append((score, c))
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[:k]]

COURSE_MD = "# Backend System Design — A Structured Course\n\n**A 15-week self-study syllabus · 6 parts · 11 modules · 23 core concepts · 35 production case studies · 17 field documents**\n\nSource material: a curated list of 10 learning libraries, 23 canonical system-design concepts, 35 production architecture write-ups, and a 17-volume field document library (interview runbooks, decision playbooks, incident postmortems, code-review patterns — ProdRescue volumes by Devrim Özcay). Every concept is paired with a hands-on lab; every case study is mapped back to the concepts it reinforces.\n\n---\n\n## 1. How this course works\n\nEach week follows the same four-step rhythm (~9 hours):\n\n| Step | Time | What you do |\n|---|---|---|\n| **Read** | 3 h | Study the module's concepts from the core reading libraries |\n| **Diagram** | 2 h | Redraw the architecture from memory — no peeking |\n| **Build** | 3 h | Implement the module's lab (small, working, real) |\n| **Design doc** | 1 h | Write a one-page answer to \"what breaks at 100× scale?\" |\n\nRules of engagement:\n\n1. **Diagram before you build.** If you can't draw it, you can't build it.\n2. **Every lab must run.** A queue that \"mostly works\" teaches you exactly-once lies.\n3. **End every module with a design doc.** One page: requirements, estimates, architecture, top 2 bottlenecks.\n4. **Case studies come after concepts, never before.** They are the exam, not the lecture.\n\nFrom Week 13 the rhythm is unchanged, but the material switches from textbooks to the **field document library** (§7): labs become drills, reviews, and written records — the same skills tested where they were learned.\n\n---\n\n## 2. Course map\n\n| Part | Module | Concepts covered | Weeks |\n|---|---|---|---|\n| I — Foundations | M01 Scaling Fundamentals | Horizontal vs Vertical Scaling; Back-of-the-Envelope Estimation | 1 |\n| I — Foundations | M02 The Request Path | Load Balancing; CDN; API Gateway; Rate Limiting | 2 |\n| II — The Data Layer | M03 Storage at Scale | Database Scaling; Replication; Sharding; Partitioning | 3–4 |\n| II — The Data Layer | M04 Consistency & Transactions | CAP Theorem; Consistency Models; Eventual Consistency; Distributed Transactions | 5 |\n| III — Performance & Resilience | M05 Caching | Caching; Cache Invalidation | 6 |\n| III — Performance & Resilience | M06 Resilience | Fault Tolerance; Idempotency & Data Latency | 7 |\n| IV — Architecture Patterns | M07 Async Systems & Coordination | Queues; Microservices; Microservices vs Monoliths; Service Discovery; Leader Election | 8–9 |\n| V — Practice | M08 Case Study Lab | 35 production architectures, in 8 themes | 10–11 |\n| V — Practice | M09 Design Workshop & Capstone | Interview runbook; capstone builds | 12 |\n| VI — The Field Manual | M10 Production Operations | Incident command; failure shapes; code review; ADRs & postmortems | 13–14 |\n| VI — The Field Manual | M11 The Senior Track | Decision frameworks; communication; leveling & offers | 15 |\n\nProgression logic: **cost math → traffic path → state → failure → interaction patterns → production proof → field judgment.** Each part assumes the previous one; don't skip ahead.\n\n---\n\n## 3. Module syllabus\n\n### Part I — Foundations\n\n#### M01 · Scaling Fundamentals (Week 1)\n\n**Goal:** reason about load mathematically before touching any architecture diagram.\n\n- **Concepts:** Horizontal vs Vertical Scaling · Back-of-the-Envelope Estimation\n- **Core questions:** When does buying a bigger box stop working? What does replication cost in latency and complexity? What is \"a lot\" of QPS, honestly?\n- **Drill:** memorize the anchor numbers: 86,400 s/day; same-region RTT ~1 ms, cross-region 50–150 ms; SSD sequential ~100 MB/s, random reads 50–100 µs; a single Postgres primary handles ~10–50K writes/s; a single Redis ~100K ops/s. Practice the capacity chain out loud: DAU → QPS → storage → bandwidth, with the sentence pattern *\"Assuming X, and assuming Y, that puts us around Z.\"*\n- **Peak multipliers** (plan for peak, not average — production systems fail at peak): single-region consumer 2.5–3×, global multi-region 1.5–2×, B2B business-hours 4–5×, flash-sale 10×+.\n- **Lab:** estimate QPS, storage growth/day, bandwidth, and cache footprint for five products: URL shortener, news feed, group chat, video streaming, ride hailing. Worked reference: 1B URLs/day = ~11.6K writes/s; at 100:1 read ratio ≈ 1.16M reads/s.\n- **Field reading:** *System Design Reality* (the 1K→10M phase narrative), *Interviews Vol IV* ch. 02 (capacity without guessing).\n- **Design doc prompt:** \"Estimate the infrastructure for a WhatsApp-class messenger at 50M DAU.\"\n\n#### M02 · The Request Path (Week 2)\n\n**Goal:** master everything between a user's tap and your server.\n\n- **Concepts:** Load Balancing (L4 vs L7, algorithms, health checks) · CDN (edge caching, pull vs push, cache headers) · API Gateway (routing, auth, aggregation) · Rate Limiting (token bucket, sliding window, distributed limiters)\n- **Core questions:** Where does TLS terminate? What belongs in the gateway vs the service? Where do you rate-limit: edge, gateway, or service?\n- **Lab:** implement a token-bucket rate limiter (Redis + Lua atomic variant in the field library); then draw the complete request path for a read-heavy product, edge to database.\n- **Field reading:** *System Design Reality* ch. 6 (rate limiting, cursor pagination), *Interview Cheatsheet* component reference.\n- **Design doc prompt:** \"Your launch-day traffic is 40× forecast. Where does the path break first, and in what order?\"\n\n### Part II — The Data Layer\n\n#### M03 · Storage at Scale (Weeks 3–4)\n\n**Goal:** make databases scale on purpose, not by accident.\n\n- **Concepts:** Database Scaling (indexes, denormalization, read replicas, SQL vs NoSQL selection) · Replication (leader–follower, multi-leader, leaderless; sync vs async; failover) · Sharding (shard-key choice, hotspots, rebalancing, consistent hashing) · Partitioning (range vs hash)\n- **Core questions:** Does your workload scale reads or writes? What makes a good shard key, and what makes a famous outage? What does resharding cost at 2 a.m.?\n- **Field rules:** the decision profile settles it — >80% reads → read replicas (reversible); >30% writes → sharding (every replica receives every write; sharding is effectively irreversible). PostgreSQL is the default until your workload proves otherwise. Shard keys are one-way doors: the shard-key decision deserves ~10× the deliberation.\n- **Lab:** build a key-value store with consistent-hashing sharding (route via *Build Your Own X*).\n- **Field reading:** *System Design Reality* ch. 2 (replicas, CQRS, sharding), *Architecture Decision Playbook* D02 + D07.\n- **Design doc prompt:** \"Shard a 10 TB user table with near-zero downtime. Walk through key choice and rebalancing.\"\n\n#### M04 · Consistency & Transactions (Week 5)\n\n**Goal:** stop using \"eventually consistent\" as an excuse; start using it as a decision.\n\n- **Concepts:** CAP Theorem (plus the PACELC intuition) · Consistency Models (strong, sequential, causal, read-your-writes, eventual) · Eventual Consistency (anti-entropy, read repair, versioning/vector clocks) · Distributed Transactions (2PC and why people fear it, Sagas, the outbox pattern)\n- **Core questions:** Which consistency model does each user-facing feature actually need? What compensates a failed saga step? Why do dual writes corrupt data?\n- **Field rules:** consistency is chosen **per operation, not per system** — strong for balance reads, inventory deduction, and uniqueness constraints; eventual for feeds, dashboards, and search indexes; read-after-write as its own requirement (session pinning, client overlay, wait-for-replication). And the sentence to never forget: *eventual consistency without a saga is data corruption with a delay.*\n- **Lab:** implement a saga with compensating actions for an order + payment two-service flow; then break it with a dual write and fix it with an outbox.\n- **Field reading:** *Interviews Vol IV* ch. 08 (consistency under partition), *Architecture Decision Playbook* D04.\n- **Design doc prompt:** \"Pick the consistency model for a shopping cart, a bank ledger, and a social feed. Defend each choice.\"\n\n### Part III — Performance & Resilience\n\n#### M05 · Caching (Week 6)\n\n**Goal:** make reads fast without making correctness subtle in a bad way.\n\n- **Concepts:** Caching (layers: browser → CDN → app → DB; patterns: cache-aside, write-through, write-behind; eviction: LRU/LFU/TTL; thundering herd) · Cache Invalidation (TTL, explicit purge, versioned keys — and why it's called one of the two hard problems)\n- **Core questions:** Which layer gives the biggest win per dollar? What happens when a hot key expires at peak? What is your invalidation story when data changes out-of-band?\n- **Field rules:** cache only when read:write > 10:1, staleness is acceptable, the computation is expensive, and projected hit rate > 50% — \"cache per-user = cache with no hits = just a slow write.\" The four-layer stack compounds (CDN → regional → in-process → DB buffer pool ≈ 99% of reads never touch disk), and **cache hit ratio is the SLO at scale**. A cache the system cannot survive without is not a cache — it is a tier of your architecture; defend the stampede path with single-flight (request coalescing), TTL jitter, and stale-while-revalidate.\n- **Lab:** add cache-aside to a real API, measure hit/miss ratios, then trigger a stampede and fix it (single-flight or locks).\n- **Field reading:** *Visual Atlas* §04 (cache patterns, stampede and the mutex), *Decision Map* D8 (when to add a cache).\n- **Design doc prompt:** \"Design the full cache stack for a product-detail page with 10M SKUs.\"\n\n#### M06 · Resilience (Week 7)\n\n**Goal:** design for the dependency that will fail — it will.\n\n- **Concepts:** Fault Tolerance (retries, timeouts, circuit breakers, bulkheads, graceful degradation, chaos testing) · Idempotency & Data Latency (at-least-once vs exactly-once, idempotency keys, deduplication, why exactly-once is a contract not a network property)\n- **Core questions:** What does your system do when the payment provider is down but reachable? Which retries make things worse (retry storms)? How do duplicate submits stay safe?\n- **Field rules:** retries need full jitter — `sleep = random(0, min(cap, base × 2^attempt))` — because fixed backoff syncs your retry batches into new spikes. Circuit breakers are a product decision (critical path: fast-fail beats slow-success; non-critical: fall back to a sensible default). Bulkheads: per-downstream connection pools contain failure. And: **read-only retries are safe; state-changing retries without idempotency are bugs.**\n- **Lab:** wrap a deliberately flaky dependency with a circuit breaker + retry with exponential backoff and jitter; verify state stays consistent under duplicates.\n- **Field reading:** *Visual Atlas* §08 (circuit breaker, jitter, bulkhead), *Decision Map* D5 (third-party outage), *Code Review Playbook* §05 (reliability omissions).\n- **Design doc prompt:** \"Make a payment API safe under duplicate submits and a 30 s provider outage.\"\n\n### Part IV — Architecture Patterns\n\n#### M07 · Async Systems & Coordination (Weeks 8–9)\n\n**Goal:** move work off the request path, and get services to agree on who's in charge.\n\n- **Concepts:** Queues (Kafka vs RabbitMQ mental models, delivery semantics, retries, dead-letter queues) · Microservices (service boundaries, data ownership) · Microservices vs Monoliths (splitting costs, the modular monolith option) · Service Discovery (registries, health checks, client-side vs server-side) · Leader Election (leases, consensus, Raft intuition)\n- **Core questions:** Which operations are sync by contract and which are only sync by habit? What breaks when two services both \"own\" the user record? Who leads when the leader is half-dead?\n- **Field rules:** Kafka's durability is a **per-topic dial**, not a global setting — `acks=0` for telemetry, `acks=1` for user events, `acks=all` for billing/audit; the configuration is the design. Team topology comes first: microservices below ~25 engineers is almost always a mistake (1–10: monolith; 10–25: modular monolith or 2–4 services; 25+: microservices if boundaries match). The database is the boundary — no DB extraction means a distributed monolith. *\"Synchronous chains are how distributed systems get slow. Asynchronous chains are how they stay debuggable.\"*\n- **Lab:** build a mini message queue with at-least-once delivery, consumer retries, and an idempotent consumer.\n- **Field reading:** *Interviews Vol IV* ch. 06–07 (fan-out, throughput), *Architecture Decision Playbook* D01 + D03, *System Design Reality* ch. 4–5.\n- **Design doc prompt:** \"Monolith or microservices for a 12-engineer startup shipping a marketplace? Write the decision memo both ways.\"\n\n### Part V — Practice\n\n#### M08 · Case Study Lab (Weeks 10–11)\n\n**Goal:** see every concept from Parts I–IV surviving contact with production.\n\nWork the 35 case studies in 8 themed sprints (full catalog in §4). Per case: 20-minute skim → redraw the architecture from memory → write two lines: *one decision you'd copy, one trade-off you'd question*.\n\n#### M09 · Design Workshop & Capstone (Week 12)\n\n**Goal:** perform under pressure, and ship one thing you built end-to-end.\n\n**The 45-minute runbook** (synthesized from the field library — memorize the shape, fill it with anything):\n\n| Clock | Phase | What you do | The losing move |\n|---|---|---|---|\n| 0:00–0:05 | **Scope** | The 90-second opening, four moves: reframe (\"Before I draw anything, I want to make sure I'm solving the right problem\"), exactly three questions — **scale**, **axis** (read-heavy / write-heavy / latency-critical / durability-critical), **scope** (\"what's explicitly out of scope?\" — the magic one) — then name your sequence and invite redirection. Write scope in a corner and refer back to it ≥3 times. | Picking up the marker at second 12 |\n| 0:05–0:10 | **Estimate** | Derive four numbers aloud in order: DAU → QPS → storage → bandwidth. \"Assuming X and assuming Y, that puts us around Z.\" State the peak multiplier. | Declaring numbers with no chain underneath |\n| 0:10–0:25 | **The spine** | One clean request→response path, the simplest thing that works. Then name the first bottleneck *before* going deep: \"Given [number], the first thing that breaks is [X], because [fundamental limit].\" | Adding cache, queue, and six services before anything demands them |\n| 0:25–0:40 | **Deep dive** | Pick by three filters: where senior trade-offs live, where capacity numbers bite, where the interviewer's axis points. Seven steps: why this component → internals → alternatives → happy path → three failure modes → operations at 3 a.m. → \"deeper, or move on?\" | Going deep on a commodity component |\n| 0:40–0:45 | **Name what breaks + defend** | Volunteer the weakness first: \"The bottleneck here is X. At 10× scale, Y breaks first. If I had more time I'd shard Z.\" Answer every \"why this?\" with the four-part sentence below. | Presenting the design as failure-free |\n\n**The four-part trade-off sentence** (the move that wins the deep phase): *\"[Choice] because [reason], not [alternative] because [its cost], accepting [this choice's cost].\"* — e.g. \"Kafka, because we need replay at this volume. If it were low-volume with complex routing, I'd use RabbitMQ. The replay requirement is what decides it.\"\n\n**The scale jump** (minute ~32, it's a reset, not a continuation): never \"add more servers.\" Name the qualitative shifts — geographic distribution (50–150 ms cross-region floor), multi-layer caching (each layer its own invalidation story), async everywhere, distributed data — and the staff-level fifth: **at 1× the bottleneck is compute; at 100× the bottleneck is coordination.**\n\n**Pushback protocol:** \"You're right to push on that — let me redo it\" is a reset, not a defeat. Pivot, don't restart: keep the board, fix the pushed piece. Defend only ~1 in 10 pushbacks, anchored to a specific constraint or number. The interviewer is grading adaptability, not the revised architecture.\n\n**The eight fatal mistakes** (self-audit before every mock): designing before scoping · demonstrating knowledge instead of judgment · covering everything at shallow depth · skipping capacity math · single points of failure · no trade-off talk · ignoring security · no observability story.\n\n- **Drills:** *Interviews Vol IV* (10 chapters = 10 drills), *Interview Cheatsheet* (framework, mistakes, 4 worked patterns: feed fan-out hybrid, URL shortener, chat, search), *Survival Kit* (opening + checklist), *45-Minute Map*, *Visual Atlas* §01 (the interview, drawn).\n- **Capstone** (via *Build Your Own X*): a Raft-based KV store with leader election · a message queue with delivery guarantees · a load balancer · a rate limiter · a URL shortener with a full design doc. Defend every major capstone decision with the four-part sentence.\n- **Interview prep layer:** work through *Tech Interview Handbook* and *Coding Interview University* in parallel from Week 8, not Week 12.\n\n### Part VI — The Field Manual\n\n#### M10 · Production Operations (Weeks 13–14)\n\n**Goal:** run what you design — incidents, reviews, and the written record.\n\n**A. The first ten minutes of an incident.** One rule: **read before you write** — every diagnostic step is read-only until the failure is classified; \"you cannot make an incident worse by looking.\" Work the order: **Classify → Confirm → Narrow → Mitigate → Verify.** Three search-space-cutting questions: *What changed?* (most incidents are something that changed in the last hour, not a spontaneous failure) · *How wide?* (endpoint / service / region / everything) · *Is it accelerating?* (accelerating means mitigate now, diagnose later). Confirm with numbers, not vibes: check the dependency's own metrics, not your latency to it; correlate the start time to a change, to the minute. Mitigate with reversible moves, **one change at a time** — three changes plus recovery teaches you nothing. And respect the capacity trap: adding instances makes retry storms, stampedes, and leaks *worse*.\n\n**B. The seven failure shapes** (recognize the shape, don't memorize incidents):\n\n| Shape | Signature | First check |\n|---|---|---|\n| Connection pool exhaustion | Everything slow, DB idle | Pool utilization / acquire-wait — not query time |\n| Retry storm | Load far above real traffic, no deploy behind it | Caller retry / backoff config |\n| Cache stampede | DB fine, then dead instantly at peak | A shared expiry timestamp |\n| Resource leak | Slow climb for hours or days, then a wall | The trend, not one snapshot |\n| Swallowed exception | Logs say success, users see failure | Catch blocks near the failure |\n| Deadlock / lock contention | Everyone waiting, no one working | Lock order, not lock count |\n| \"Everything is green\" | Dashboards fine, users blocked | One real user path, end to end |\n\n**C. Case study — The 02:43 Outage** (read the full postmortem, then debrief): payments P99 climbs 280 ms → 4.2 s; the connection pool saturates; every DB dashboard looks healthy. 35 minutes go missing in the wrong layer (EXPLAIN ANALYZE: all queries <2 ms; zero blocking locks) — until the senior's one question: *\"What are the ten connections actually doing right now?\"* Answer: 8 of 10 connections `idle in transaction`, `wait_event_type = Client` — the app, not the DB, holds them. Root cause: a synchronous fraud-API HTTP call inside `@Transactional` — ~55 ms of DB work holding each connection ~8 s while the third party degraded; a **31× throughput collapse**. The fix is three structural lines (move the call before the transaction); the hardening is an audit of all 16 transactional methods, a circuit breaker, and a 30 s → 10 s acquisition timeout. The rule it teaches: **transaction duration equals the duration of the slowest synchronous thing inside it.** And the meta-lesson: the same shape was diagnosed in 4h12m, then 1h47m, 38m, 11m, 7m, 4m, 2m, and finally 90 seconds — pattern recognition is exposure, compressed.\n\n**D. Code review as an incident filter.** The senior question: *\"What would have to be true for this to break in production six months from now?\"* Twenty patterns across eight families — correctness slips (unreachable returns, wrong default branches), concurrency (read-modify-write races, unsafe lazy singletons), database anti-patterns (N+1 hidden behind getters, missing index without `CREATE INDEX CONCURRENTLY`, transactions held across HTTP calls), API contract drift (breaking renames, optional → required), reliability omissions (HTTP clients without timeouts, retries without idempotency keys, sync calls on the critical path), security slips (log injection, IDOR / tenant scoping from request bodies), test theater (assertions generated from the buggy output, mocks that test themselves). Reviewer discipline: 0–3 load-bearing comments per PR; block for data loss, security, breaking APIs, and migration order; approve-with-concerns for the rest; **bring data, not taste.**\n\n**E. Writing it down.** The ADR, six sections: decision-statement title, status, context (≤2 paragraphs), decision, alternatives considered (the section lazy authors cut and future readers most need), consequences — readable in five minutes, in version control next to the code. The postmortem: blameless means actions, not actors (\"the deployment was approved at 14:32\"); **max 3 action items**, each with a named owner and date; review the corpus quarterly and invest in the recurring category.\n\n- **Labs:** run the 7-shape triage against the 02:43 timeline and write its postmortem; review a seeded PR and leave exactly three load-bearing comments; write the ADR for your M03 sharding decision.\n- **Field reading:** *Production Incident Field Card*, *The 02:43 Outage*, *Code Review Playbook*, *Decision Map* D1–D6 + D12–D15 (rollback default rule, OOMKilled causes, load average ≠ CPU utilization, the AI-inference-in-production trap), *Staff Engineers Architecture Playbook* Part IV.\n- **Design doc prompt:** \"Make the fraud-check pattern impossible: what changes at the code, review, and runtime layers?\"\n\n#### M11 · The Senior Track (Week 15)\n\n**Goal:** judgment, made visible — decisions, communication, and the offer.\n\n**A. The decision framework.** Before any architecture decision, four questions: *Is this reversible? What is the blast radius? What does it cost to not decide? What does it constrain downstream?* Two-way doors vs one-way doors; the asymmetry rule (irreversible + wide blast radius deserves ~10× the deliberation). Five cost dimensions — infrastructure is the only one on the slide, and rarely the largest: engineering time, operational tax (\"who is on call for this in three years?\"), cognitive load, opportunity cost. *\"Most bad architecture decisions are not made deliberately. They are made by default.\"*\n\n**B. Eight decisions as drills** — each with the rule that settles it and the loss case that proves it:\n\n| Decision | The rule that settles it | The loss case |\n|---|---|---|\n| Kafka vs RabbitMQ | Throughput / replay / ordering / ops — under ~5K msg/s the choice doesn't differentiate; replay needs a log | 500 emails/min on a 3-broker Kafka cluster: ~10× the cost of RabbitMQ |\n| PostgreSQL vs DynamoDB | Access-pattern predictability decides; Postgres is the default until proven otherwise; after 3–4 GSIs \"you are operating five tables\" | 200 req/s SaaS \"for web scale\": 5 GSIs by month 9, 4-month migration back to Postgres |\n| Monolith vs microservices | Team topology first (Conway); <25 engineers ≈ almost always a mistake; modular monolith keeps the door open | 12 engineers, 12 services: every feature touched 3+, 8 merged back, ~2 engineer-years lost |\n| Consistency per operation | Strong for money, inventory, uniqueness; eventual for feeds and dashboards; read-after-write is its own requirement | Eventually-consistent inventory cache oversold 4,000 units in a flash sale |\n| REST / gRPC / GraphQL | By consumer profile; most systems need one style, a few need two, almost nothing needs three | Three API styles over one data model: drift, tripled on-call, 2 of 3 deprecated |\n| Sync vs async | Latency budget + failure cost + idempotency decide; async-by-default for anything the user doesn't wait on | Payment auth made async: silent failures, 2 months of reconciliation infra |\n| Replicas vs sharding | >80% reads → replicas (reversible); >30% writes → sharding (effectively irreversible); analyze hot keys first | Sharded at 8K writes/s, 95% reads: ~1 engineer-year round trip for no benefit |\n| Build vs buy | Core → build; context → buy; critical-but-not-core → deliberate, time-boxed, with documented exit criteria | Feature flags built because \"the vendor was too expensive\": ~1 engineer-year wasted |\n\n**C. Communication — the radius of thinking.** What committees actually measure is how far the consequences of your decisions traveled: **team → org → company** (the scope ladder). The highest-leverage sentence: *\"We considered [X], and chose not to, because [constraint] mattered more than [what X would have given us].\"* Impact formula: **reach × severity × business value** — and if you lack the number, show the estimation method instead of inventing one. Phrase swaps: \"I built X\" → \"I chose X over Y, because Z mattered more\"; \"It went well\" → \"It hit [metric] against a baseline of [metric]\"; \"I escalated it\" → a documented last resort, taken with data. The eight failure patterns to self-audit against: too technical · no system thinking · escalated as first move · can't quantify · process without outcome · no trade-offs named · no mentorship signal · no story about being wrong.\n\n**D. The offer.** Level is the biggest lever — negotiate the level before the number. Scope and ownership over title. The real money moves in equity and sign-on, not base; competing offers in writing are the whole game. Never accept on the call — *\"the relief is the expensive emotion.\"* Compensation signals, weak vs strong: writes the most code → reduces the need for code; says yes to everything → says no, with a reason; knows the most tools → knows which tool not to use.\n\n- **Labs:** run three decision-matrix drills aloud (pick any three rows above); rewrite two of your own project stories through the scope ladder and phrase swaps; run the capstone defense — every major decision answered with the four questions plus the trade-off sentence.\n- **Field reading:** *Backend Architecture Decision Playbook* (all 8 decisions), *Senior Backend Decision Map* (20 junior/senior defaults), *Staff Engineers Architecture Playbook* (Part I–III: framework + case studies), *Staff Engineer Communication Playbook*, *Staff Engineer Interview Playbook*, *What the $250K Engineer Knows*, *Decision Cards*, *Senior Backend Field Cards*.\n- **Design doc prompt:** \"The decision record of your capstone: one ADR per major choice, each with the alternative you rejected and the cost you accepted.\"\n\n---\n\n## 4. Case study catalog — 35 architectures in 8 themes\n\n| # | Theme | Cases | Reinforces |\n|---|---|---|---|\n| 1 | **Real-Time & Messaging** | Discord (Trillion Message Indexing) · Twilio (Exactly-Once Delivery) · Slack (Cellular Architecture Migration) · Netflix (Distributed Tracing Infrastructure) | M04 consistency, M06 idempotency, M07 queues, observability |\n| 2 | **Storage & Data Infrastructure** | Dropbox (Magic Pocket) · GitHub (Distributed Storage System) · Airbnb (Key-Value Architecture) · Datadog (Husky Event Store) | M03 storage/sharding, M04 consistency, M07 queues |\n| 3 | **Edge & Global Scale** | Cloudflare (Global Edge Architecture) · Pinterest (Cache Infrastructure Scaling) · eBay (Distributed Listing) · Walmart (Autocomplete Backend Rebuild) | M02 CDN/load balancing, M05 caching, M03 partitioning |\n| 4 | **Payments & Financial Reliability** | Stripe (Database Migration Platform) · PayPal (Kafka Scaling) · Razorpay (Reliable Dual Writes) · Coinbase (Solana Processing) · PhonePe (Distributed Job Scheduler) · Capital One (Resilient Systems) | M04 transactions/outbox, M06 idempotency & resilience, M07 queues |\n| 5 | **Migration Journeys** | Shopify (Sharded Monolith) · DoorDash (Microservices Migration) · Zomato (Billing Platform Scaling) | M03 sharding, M07 monolith↔microservices, M06 fault tolerance |\n| 6 | **Event-Driven Architectures** | AWS (Event-Driven Architecture) · Meta (Distributed Priority Queue) · Salesforce (Guaranteed Data Delivery) · Canva (Analytics Event Pipeline) · Etsy (Kafka Zonal Resiliency) | M07 queues/event-driven, M06 fault tolerance |\n| 7 | **Platform Engineering & Internal Infrastructure** | Google (System Design Principles) · Microsoft (Platform Engineering Paths) · Atlassian (Cloud Engineering) · Expedia (Configuration Management Platform) · Adobe (Unified Search Architecture) | M02 API gateway, M07 service discovery, organizational design |\n| 8 | **Consumer Apps at Scale** | Uber (Rider App Architecture) · Spotify (Backend Infrastructure) · Figma (Multi-Database Scaling) · Instacart (Multi-Database Scaling) | M03 database scaling, M05 caching, M02 request path |\n\nReading order note: Theme 1–4 map directly onto Parts II–III; read those first, then 5–8.\n\n---\n\n## 5. The 15-week schedule\n\n| Week | Focus | Deliverable |\n|---|---|---|\n| 1 | M01 Scaling fundamentals | Estimation drill sheet + 50M-DAU messenger estimate |\n| 2 | M02 Request path | Token-bucket rate limiter + full request-path diagram |\n| 3 | M03 Database scaling & replication | Read replica setup notes + failover walkthrough |\n| 4 | M03 Sharding & partitioning | Consistent-hashing KV store (lab) |\n| 5 | M04 Consistency & transactions | Saga lab + consistency-model cheat sheet |\n| 6 | M05 Caching | Cache-aside lab with hit-rate measurements + stampede fix |\n| 7 | M06 Resilience | Circuit-breaker lab + payment-API resilience doc |\n| 8 | M07 Queues & event-driven | Mini message queue with delivery guarantees |\n| 9 | M07 Microservices & coordination | Monolith-vs-microservices decision memo + Raft reading |\n| 10 | M08 Case sprint A | Teardowns: Themes 1–4 (18 cases) |\n| 11 | M08 Case sprint B | Teardowns: Themes 5–8 (17 cases) |\n| 12 | M09 Capstone + mock interviews | Capstone repo + two timed mock designs |\n| 13 | M10 Incident response | 7-shape triage run against the 02:43 timeline + postmortem draft |\n| 14 | M10 Code review & written record | 3-comment review lab + capstone ADR |\n| 15 | M11 The senior track | Decision drills + capstone defense (four questions + trade-off sentences) |\n\n---\n\n## 6. Core reading libraries (the 10 source repos)\n\n| Library | Role in this course |\n|---|---|\n| System Design Academy | Core curriculum text for Parts I–IV |\n| Developer Roadmaps | Track progress; place yourself on the backend map |\n| Tech Interview Handbook | Interview layer for M09 |\n| Coding Interview University | CS-fundamentals refresher behind every module |\n| Build Your Own X | Source of every lab and the capstone |\n| Engineering Leadership | Context for Part IV org-level trade-offs |\n| Path to Senior Engineer Handbook | Leveling context: why senior engineers think in trade-offs |\n| freeCodeCamp | Prerequisite refresh (networking, databases, APIs) |\n| Public APIs | Real data sources for capstone projects |\n| Free Programming Books | Deep reference reading (DDIA and friends) |\n\nThe original curated list circulates with shortened `lnkd.in` links; the full list is preserved verbatim in the appendix below.\n\n---\n\n## 7. The field document library (17 volumes)\n\nA second layer of course material: interview runbooks, decision playbooks, incident postmortems, and code-review patterns. The ProdRescue volumes are by Devrim Özcay; the library was provided with the course material.\n\n| # | Document | Type | What it gives the course |\n|---|---|---|---|\n| 1 | The 45-Minute Map | Interview runbook | The time-boxed shape of the design round (M09) |\n| 2 | System Design Interview Cheatsheet | Cheatsheet | 80/20 framework, the 8 fatal mistakes, capacity formulas, 4 worked patterns (M01, M09) |\n| 3 | System Design Interview Survival Kit | Survival guide | The 90-second opening, 5 rejection patterns, prompt-pattern table, round checklist (M09) |\n| 4 | System Design Interviews Vol IV | Drill book | 10 drills: opening, capacity, depth vs breadth, trade-off naming, bottleneck-first, fan-out, throughput, consistency under partition, scale jump, pushback (M01, M04, M09) |\n| 5 | System Design Visual Atlas | Visual atlas | 36 reference diagrams, one per pattern — the picture for each lesson (all modules) |\n| 6 | The Backend Architecture Decision Playbook | Decision playbook | 8 fully-decoded decisions with matrices, win/loss cases, anti-patterns (M03, M04, M07, M11) |\n| 7 | The Senior Backend Decision Map | Decision map | 20 junior-path vs senior-path default behaviors, from 2 a.m. incidents to staff interviews (M10, M11) |\n| 8 | Staff Engineers Architecture Playbook | Architecture playbook | The four-question decision framework, reversibility/blast-radius maps, five cost dimensions, 4 production case studies, ADR + postmortem templates (M10, M11) |\n| 9 | The Staff Engineer Communication Playbook | Communication playbook | The radius of thinking, scope ladder, trade-off sentence, phrase swaps, 8 failure patterns (M11) |\n| 10 | Staff Engineer Interview Playbook | Interview playbook | Staff-level answer patterns, impact formula, 4 failure patterns, 5 real Q&As (M11) |\n| 11 | What The $250K Engineer Knows | Career guide | 8 judgment moments where compensation actually moves (M11) |\n| 12 | Senior Engineer Decision Cards | Field cards | Pocket cards: the first ten minutes, the 45-minute clock, before you sign (M09, M10, M11) |\n| 13 | Senior Backend Field Cards | Field cards | Pocket procedures for the 2 a.m. incident, the design interview, and the offer (M10, M11) |\n| 14 | Production Incident Field Card | Field card | The 10-minute triage order and 7 failure shapes (M10) |\n| 15 | The 02:43 Outage | Incident case study | Full narrated postmortem: connection-pool exhaustion via an external call inside a transaction (M10) |\n| 16 | Code Review Playbook | Playbook | 20 review patterns across 8 families + reviewer judgment (M10) |\n| 17 | 09 System Design Reality | Scaling essay | The 1K → 10M user evolution: what actually breaks at each phase (M01, M02, M03, M05, M07) |\n\n---\n\n## Appendix · Source links, verbatim from the material\n\n**Learning libraries (10):**\n\n1. System design academy — https://lnkd.in/eKATU6QV\n2. Public APIs — https://lnkd.in/epWSyzqs\n3. Tech interview handbook — https://lnkd.in/e7EjsJNF\n4. Coding interview university — https://lnkd.in/evJSNCPE\n5. Engineering leadership — https://lnkd.in/ePCzV3zF\n6. Freecodecamp — https://lnkd.in/e_4pA8xV\n7. Developer roadmaps — https://lnkd.in/e9MuB_Yg\n8. Path to senior engineer handbook — https://lnkd.in/exkJCxVi\n9. Free programming books — https://lnkd.in/eXAzAJ3M\n10. Build your own x — https://lnkd.in/ekZQbTPz\n\n**System design concepts (23):**\n\n1. Load Balancing — https://lnkd.in/gH9rdjCx\n2. CDN — https://lnkd.in/g83A7-rM\n3. Caching — https://lnkd.in/gTjxhv2V\n4. Cache Invalidation — https://lnkd.in/geC955AY\n5. Rate Limiting — https://lnkd.in/gWqJzCNJ\n6. API Gateway — https://lnkd.in/gBNKpecH\n7. CAP Theorem — https://lnkd.in/g4yFYkEi\n8. Sharding — https://lnkd.in/gFi23iNV\n9. Replication — https://lnkd.in/gikkrmNp\n10. Partitioning — https://lnkd.in/gQhJS8ii\n11. Queues — https://lnkd.in/gPGiuxtu\n12. Microservices — https://lnkd.in/gZfYV2Qu\n13. Microservices Vs Monoliths — https://lnkd.in/gM-dKE3D\n14. Fault Tolerance — https://lnkd.in/gdamMmtc\n15. Database Scaling — https://lnkd.in/ghq4v_gQ\n16. Service Discovery — https://lnkd.in/gjfbNVBe\n17. Consistency models — https://lnkd.in/gGkMENA3\n18. Eventual Consistency — https://lnkd.in/gdSn54SK\n19. Distributed Transactions — https://lnkd.in/gTc8pSbH\n20. Leader Election — https://lnkd.in/g-kwhzSb\n21. Horizontal vs Vertical Scaling — https://lnkd.in/gW-Vi9Qt\n22. Back of the Envelope Estimation — https://lnkd.in/gQ6vtM3U\n23. Idempotency, Data Latency & Finale — https://lnkd.in/gapgNSgh\n\n**Company architecture case studies (35):**\n\n1. Google System Design Principles — https://lnkd.in/gPKFwSYD\n2. Meta Distributed Priority Queue — https://lnkd.in/gBBr4Vjq\n3. Microsoft Platform Engineering Paths — https://lnkd.in/gymvyfbd\n4. Adobe Unified Search Architecture — https://lnkd.in/g_SNVuzE\n5. Salesforce Guaranteed Data Delivery — https://lnkd.in/gxCVtXZu\n6. AWS Event Driven Architecture — https://lnkd.in/gT463eWY\n7. Netflix Distributed Tracing Infrastructure — https://lnkd.in/gESgRhWU\n8. Uber Rider App Architecture — https://lnkd.in/gGbxqbpU\n9. Airbnb Key Value Architecture — https://lnkd.in/gqTSagR4\n10. Dropbox Magic Pocket Architecture — https://lnkd.in/gfdfk7FV\n11. Pinterest Cache Infrastructure Scaling — https://lnkd.in/g3NZnxAm\n12. Slack Cellular Architecture Migration — https://lnkd.in/gtnkNEzF\n13. Spotify Backend Infrastructure Architecture — https://lnkd.in/gCebV4sR\n14. Cloudflare Global Edge Architecture — https://lnkd.in/gfAq7JTH\n15. Stripe Database Migration Platform — https://lnkd.in/gVvP7VWQ\n16. Shopify Sharded Monolith Changes — https://lnkd.in/g_KZ-BA4\n17. DoorDash Microservices Migration Journey — https://lnkd.in/gBC5E3g2\n18. Discord Trillion Message Indexing — https://lnkd.in/gRkk_d9G\n19. Twilio Exactly Once Delivery — https://lnkd.in/ga7Zfank\n20. Datadog Husky Event Store — https://lnkd.in/gWcZgw3S\n21. Atlassian Cloud Engineering Architecture — https://lnkd.in/gyaGJxHY\n22. PayPal Kafka Scaling Architecture — https://lnkd.in/gBRT8R-P\n23. eBay Distributed Listing Architecture — https://lnkd.in/gqUVQRiW\n24. Walmart Autocomplete Backend Rebuild — https://lnkd.in/gbVKZT2p\n25. Capital One Resilient Systems — https://lnkd.in/gSv385XX\n26. Canva Analytics Event Pipeline — https://lnkd.in/gReCsAkW\n27. Figma Multi Database Scaling — https://lnkd.in/gQqayzyk\n28. Razorpay Reliable Dual Writes — https://lnkd.in/gRiV9ypn\n29. PhonePe Distributed Job Scheduler — https://lnkd.in/gZ4ZVDkN\n30. Zomato Billing Platform Scaling — https://lnkd.in/g9kcikQy\n31. Coinbase Solana Processing Architecture — https://lnkd.in/gyYwXm8g\n32. Etsy Kafka Zonal Resiliency — https://lnkd.in/gJcnfTer\n33. Expedia Configuration Management Platform — https://lnkd.in/gkj5GerG\n34. Instacart Multi Database Scaling — https://lnkd.in/gUfawb2B\n35. GitHub Distributed Storage System — https://lnkd.in/gDAAq6RP\n"

KB = CourseKB(COURSE_MD)

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "glm-4.6")
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get(
        "ALLOWED_ORIGINS",
        "https://olivistart.com,https://ericzhoun.github.io,http://localhost:3000,http://127.0.0.1:3000",
    ).split(",") if o.strip()
]

app = FastAPI(title="DeepTutor Course Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

SYSTEM_PROMPT = (
    "You are DeepTutor, the AI tutor for the 'Backend System Design' course "
    "(a 15-week, 11-module backend engineering curriculum).\n"
    "Rules:\n"
    "1. Ground every answer in the COURSE EXCERPTS provided in the user message.\n"
    "2. Cite module codes like [M03] for claims drawn from the course.\n"
    "3. If the question goes beyond the course, say so in one clause, then answer briefly from general knowledge.\n"
    "4. Be concrete: rules, numbers, trade-offs, failure modes. No filler."
)


class TutorReq(BaseModel):
    question: str
    module: Optional[str] = None
    stream: bool = False


class QuizReq(BaseModel):
    module: Optional[str] = None
    count: int = 5


class ExplainReq(BaseModel):
    concept: str
    level: str = "simple"


def _llm_configured() -> bool:
    return bool(LLM_API_KEY)


def _messages_for(question: str, module: Optional[str], extra_system: str = "") -> list:
    chunks = KB.retrieve(question, module=module, k=4)
    excerpts = "\n\n".join(f"[{c['module']} · {c['title']}]\n{c['text']}" for c in chunks) or "(no excerpts matched)"
    system = SYSTEM_PROMPT + ("\n\n" + extra_system if extra_system else "")
    user = f"COURSE EXCERPTS:\n{excerpts}\n\nQUESTION: {question}"
    if module:
        user += f"\n(The learner is currently studying module {module} — prefer excerpts from it.)"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], chunks


async def _chat(payload: dict):
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


def _extract_json(text: str):
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start:end + 1])


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "deeptutor-course-backend",
        "llm": {"configured": _llm_configured(), "base_url": LLM_BASE_URL, "model": LLM_MODEL},
        "kb": {"chunks": len(KB.chunks), "modules": KB.modules},
    }


@app.get("/api/outline")
async def outline():
    return {"modules": KB.modules}


@app.post("/api/tutor")
async def tutor(req: TutorReq):
    if not _llm_configured():
        return JSONResponse(status_code=503, content={"error": "LLM_API_KEY is not configured on this deployment."})
    messages, chunks = _messages_for(req.question, req.module)
    payload = {"model": LLM_MODEL, "messages": messages, "temperature": 0.3, "stream": req.stream}
    sources = [{"module": c["module"], "title": c["title"]} for c in chunks]

    if not req.stream:
        data = await _chat(payload)
        answer = data["choices"][0]["message"]["content"]
        return {"answer": answer, "sources": sources, "model": LLM_MODEL}

    async def gen():
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                json=payload,
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        delta = json.loads(data)["choices"][0]["delta"].get("content", "")
                    except Exception:
                        continue
                    if delta:
                        yield f"data: {json.dumps({'delta': delta})}\n\n"
        yield f"data: {json.dumps({'sources': sources, 'done': True})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/quiz")
async def quiz(req: QuizReq):
    if not _llm_configured():
        return JSONResponse(status_code=503, content={"error": "LLM_API_KEY is not configured on this deployment."})
    count = max(1, min(req.count, 10))
    topic = f"Focus on module {req.module}." if req.module else "Cover any course modules."
    q = (
        f"Generate {count} multiple-choice quiz questions strictly from the course excerpts. "
        f"{topic} Each question must be answerable from the excerpts alone. "
        'Return ONLY a JSON object: {"questions": [{"question": str, "options": [str, str, str, str], '
        '"answer": "A"|"B"|"C"|"D", "explanation": str}]}. '
        "Vary which option is correct across questions. Explanations: 1-2 sentences, cite module codes."
    )
    messages, chunks = _messages_for(q, req.module, extra_system="Output raw JSON only — no markdown fences, no prose.")
    data = await _chat({"model": LLM_MODEL, "messages": messages, "temperature": 0.5})
    try:
        parsed = _extract_json(data["choices"][0]["message"]["content"])
        questions = parsed.get("questions", [])[:count]
    except Exception:
        return JSONResponse(status_code=502, content={"error": "Model returned unparseable quiz JSON. Try again."})
    for i, item in enumerate(questions):
        item["id"] = f"gen-{i + 1}"
    return {"questions": questions, "sources": [{"module": c["module"], "title": c["title"]} for c in chunks]}


@app.post("/api/explain")
async def explain(req: ExplainReq):
    if not _llm_configured():
        return JSONResponse(status_code=503, content={"error": "LLM_API_KEY is not configured on this deployment."})
    level = "simple, with one concrete example" if req.level == "simple" else "in depth: mechanics, numbers, trade-offs, failure modes"
    q = f"Explain the concept '{req.concept}' at a {level}, grounded in the course excerpts."
    messages, chunks = _messages_for(q, None)
    data = await _chat({"model": LLM_MODEL, "messages": messages, "temperature": 0.3})
    return {
        "answer": data["choices"][0]["message"]["content"],
        "sources": [{"module": c["module"], "title": c["title"]} for c in chunks],
    }
