# Backend System Design — A Structured Course

**A 15-week self-study syllabus · 6 parts · 11 modules · 23 core concepts · 35 production case studies · 17 field documents**

Source material: a curated list of 10 learning libraries, 23 canonical system-design concepts, 35 production architecture write-ups, and a 17-volume field document library (interview runbooks, decision playbooks, incident postmortems, code-review patterns — ProdRescue volumes by Devrim Özcay). Every concept is paired with a hands-on lab; every case study is mapped back to the concepts it reinforces.

---

## 1. How this course works

Each week follows the same four-step rhythm (~9 hours):

| Step | Time | What you do |
|---|---|---|
| **Read** | 3 h | Study the module's concepts from the core reading libraries |
| **Diagram** | 2 h | Redraw the architecture from memory — no peeking |
| **Build** | 3 h | Implement the module's lab (small, working, real) |
| **Design doc** | 1 h | Write a one-page answer to "what breaks at 100× scale?" |

Rules of engagement:

1. **Diagram before you build.** If you can't draw it, you can't build it.
2. **Every lab must run.** A queue that "mostly works" teaches you exactly-once lies.
3. **End every module with a design doc.** One page: requirements, estimates, architecture, top 2 bottlenecks.
4. **Case studies come after concepts, never before.** They are the exam, not the lecture.

From Week 13 the rhythm is unchanged, but the material switches from textbooks to the **field document library** (§7): labs become drills, reviews, and written records — the same skills tested where they were learned.

---

## 2. Course map

| Part | Module | Concepts covered | Weeks |
|---|---|---|---|
| I — Foundations | M01 Scaling Fundamentals | Horizontal vs Vertical Scaling; Back-of-the-Envelope Estimation | 1 |
| I — Foundations | M02 The Request Path | Load Balancing; CDN; API Gateway; Rate Limiting | 2 |
| II — The Data Layer | M03 Storage at Scale | Database Scaling; Replication; Sharding; Partitioning | 3–4 |
| II — The Data Layer | M04 Consistency & Transactions | CAP Theorem; Consistency Models; Eventual Consistency; Distributed Transactions | 5 |
| III — Performance & Resilience | M05 Caching | Caching; Cache Invalidation | 6 |
| III — Performance & Resilience | M06 Resilience | Fault Tolerance; Idempotency & Data Latency | 7 |
| IV — Architecture Patterns | M07 Async Systems & Coordination | Queues; Microservices; Microservices vs Monoliths; Service Discovery; Leader Election | 8–9 |
| V — Practice | M08 Case Study Lab | 35 production architectures, in 8 themes | 10–11 |
| V — Practice | M09 Design Workshop & Capstone | Interview runbook; capstone builds | 12 |
| VI — The Field Manual | M10 Production Operations | Incident command; failure shapes; code review; ADRs & postmortems | 13–14 |
| VI — The Field Manual | M11 The Senior Track | Decision frameworks; communication; leveling & offers | 15 |

Progression logic: **cost math → traffic path → state → failure → interaction patterns → production proof → field judgment.** Each part assumes the previous one; don't skip ahead.

---

## 3. Module syllabus

### Part I — Foundations

#### M01 · Scaling Fundamentals (Week 1)

**Goal:** reason about load mathematically before touching any architecture diagram.

- **Concepts:** Horizontal vs Vertical Scaling · Back-of-the-Envelope Estimation
- **Core questions:** When does buying a bigger box stop working? What does replication cost in latency and complexity? What is "a lot" of QPS, honestly?
- **Drill:** memorize the anchor numbers: 86,400 s/day; same-region RTT ~1 ms, cross-region 50–150 ms; SSD sequential ~100 MB/s, random reads 50–100 µs; a single Postgres primary handles ~10–50K writes/s; a single Redis ~100K ops/s. Practice the capacity chain out loud: DAU → QPS → storage → bandwidth, with the sentence pattern *"Assuming X, and assuming Y, that puts us around Z."*
- **Peak multipliers** (plan for peak, not average — production systems fail at peak): single-region consumer 2.5–3×, global multi-region 1.5–2×, B2B business-hours 4–5×, flash-sale 10×+.
- **Lab:** estimate QPS, storage growth/day, bandwidth, and cache footprint for five products: URL shortener, news feed, group chat, video streaming, ride hailing. Worked reference: 1B URLs/day = ~11.6K writes/s; at 100:1 read ratio ≈ 1.16M reads/s.
- **Field reading:** *System Design Reality* (the 1K→10M phase narrative), *Interviews Vol IV* ch. 02 (capacity without guessing).
- **Design doc prompt:** "Estimate the infrastructure for a WhatsApp-class messenger at 50M DAU."

#### M02 · The Request Path (Week 2)

**Goal:** master everything between a user's tap and your server.

- **Concepts:** Load Balancing (L4 vs L7, algorithms, health checks) · CDN (edge caching, pull vs push, cache headers) · API Gateway (routing, auth, aggregation) · Rate Limiting (token bucket, sliding window, distributed limiters)
- **Core questions:** Where does TLS terminate? What belongs in the gateway vs the service? Where do you rate-limit: edge, gateway, or service?
- **Lab:** implement a token-bucket rate limiter (Redis + Lua atomic variant in the field library); then draw the complete request path for a read-heavy product, edge to database.
- **Field reading:** *System Design Reality* ch. 6 (rate limiting, cursor pagination), *Interview Cheatsheet* component reference.
- **Design doc prompt:** "Your launch-day traffic is 40× forecast. Where does the path break first, and in what order?"

### Part II — The Data Layer

#### M03 · Storage at Scale (Weeks 3–4)

**Goal:** make databases scale on purpose, not by accident.

- **Concepts:** Database Scaling (indexes, denormalization, read replicas, SQL vs NoSQL selection) · Replication (leader–follower, multi-leader, leaderless; sync vs async; failover) · Sharding (shard-key choice, hotspots, rebalancing, consistent hashing) · Partitioning (range vs hash)
- **Core questions:** Does your workload scale reads or writes? What makes a good shard key, and what makes a famous outage? What does resharding cost at 2 a.m.?
- **Field rules:** the decision profile settles it — >80% reads → read replicas (reversible); >30% writes → sharding (every replica receives every write; sharding is effectively irreversible). PostgreSQL is the default until your workload proves otherwise. Shard keys are one-way doors: the shard-key decision deserves ~10× the deliberation.
- **Lab:** build a key-value store with consistent-hashing sharding (route via *Build Your Own X*).
- **Field reading:** *System Design Reality* ch. 2 (replicas, CQRS, sharding), *Architecture Decision Playbook* D02 + D07.
- **Design doc prompt:** "Shard a 10 TB user table with near-zero downtime. Walk through key choice and rebalancing."

#### M04 · Consistency & Transactions (Week 5)

**Goal:** stop using "eventually consistent" as an excuse; start using it as a decision.

- **Concepts:** CAP Theorem (plus the PACELC intuition) · Consistency Models (strong, sequential, causal, read-your-writes, eventual) · Eventual Consistency (anti-entropy, read repair, versioning/vector clocks) · Distributed Transactions (2PC and why people fear it, Sagas, the outbox pattern)
- **Core questions:** Which consistency model does each user-facing feature actually need? What compensates a failed saga step? Why do dual writes corrupt data?
- **Field rules:** consistency is chosen **per operation, not per system** — strong for balance reads, inventory deduction, and uniqueness constraints; eventual for feeds, dashboards, and search indexes; read-after-write as its own requirement (session pinning, client overlay, wait-for-replication). And the sentence to never forget: *eventual consistency without a saga is data corruption with a delay.*
- **Lab:** implement a saga with compensating actions for an order + payment two-service flow; then break it with a dual write and fix it with an outbox.
- **Field reading:** *Interviews Vol IV* ch. 08 (consistency under partition), *Architecture Decision Playbook* D04.
- **Design doc prompt:** "Pick the consistency model for a shopping cart, a bank ledger, and a social feed. Defend each choice."

### Part III — Performance & Resilience

#### M05 · Caching (Week 6)

**Goal:** make reads fast without making correctness subtle in a bad way.

- **Concepts:** Caching (layers: browser → CDN → app → DB; patterns: cache-aside, write-through, write-behind; eviction: LRU/LFU/TTL; thundering herd) · Cache Invalidation (TTL, explicit purge, versioned keys — and why it's called one of the two hard problems)
- **Core questions:** Which layer gives the biggest win per dollar? What happens when a hot key expires at peak? What is your invalidation story when data changes out-of-band?
- **Field rules:** cache only when read:write > 10:1, staleness is acceptable, the computation is expensive, and projected hit rate > 50% — "cache per-user = cache with no hits = just a slow write." The four-layer stack compounds (CDN → regional → in-process → DB buffer pool ≈ 99% of reads never touch disk), and **cache hit ratio is the SLO at scale**. A cache the system cannot survive without is not a cache — it is a tier of your architecture; defend the stampede path with single-flight (request coalescing), TTL jitter, and stale-while-revalidate.
- **Lab:** add cache-aside to a real API, measure hit/miss ratios, then trigger a stampede and fix it (single-flight or locks).
- **Field reading:** *Visual Atlas* §04 (cache patterns, stampede and the mutex), *Decision Map* D8 (when to add a cache).
- **Design doc prompt:** "Design the full cache stack for a product-detail page with 10M SKUs."

#### M06 · Resilience (Week 7)

**Goal:** design for the dependency that will fail — it will.

- **Concepts:** Fault Tolerance (retries, timeouts, circuit breakers, bulkheads, graceful degradation, chaos testing) · Idempotency & Data Latency (at-least-once vs exactly-once, idempotency keys, deduplication, why exactly-once is a contract not a network property)
- **Core questions:** What does your system do when the payment provider is down but reachable? Which retries make things worse (retry storms)? How do duplicate submits stay safe?
- **Field rules:** retries need full jitter — `sleep = random(0, min(cap, base × 2^attempt))` — because fixed backoff syncs your retry batches into new spikes. Circuit breakers are a product decision (critical path: fast-fail beats slow-success; non-critical: fall back to a sensible default). Bulkheads: per-downstream connection pools contain failure. And: **read-only retries are safe; state-changing retries without idempotency are bugs.**
- **Lab:** wrap a deliberately flaky dependency with a circuit breaker + retry with exponential backoff and jitter; verify state stays consistent under duplicates.
- **Field reading:** *Visual Atlas* §08 (circuit breaker, jitter, bulkhead), *Decision Map* D5 (third-party outage), *Code Review Playbook* §05 (reliability omissions).
- **Design doc prompt:** "Make a payment API safe under duplicate submits and a 30 s provider outage."

### Part IV — Architecture Patterns

#### M07 · Async Systems & Coordination (Weeks 8–9)

**Goal:** move work off the request path, and get services to agree on who's in charge.

- **Concepts:** Queues (Kafka vs RabbitMQ mental models, delivery semantics, retries, dead-letter queues) · Microservices (service boundaries, data ownership) · Microservices vs Monoliths (splitting costs, the modular monolith option) · Service Discovery (registries, health checks, client-side vs server-side) · Leader Election (leases, consensus, Raft intuition)
- **Core questions:** Which operations are sync by contract and which are only sync by habit? What breaks when two services both "own" the user record? Who leads when the leader is half-dead?
- **Field rules:** Kafka's durability is a **per-topic dial**, not a global setting — `acks=0` for telemetry, `acks=1` for user events, `acks=all` for billing/audit; the configuration is the design. Team topology comes first: microservices below ~25 engineers is almost always a mistake (1–10: monolith; 10–25: modular monolith or 2–4 services; 25+: microservices if boundaries match). The database is the boundary — no DB extraction means a distributed monolith. *"Synchronous chains are how distributed systems get slow. Asynchronous chains are how they stay debuggable."*
- **Lab:** build a mini message queue with at-least-once delivery, consumer retries, and an idempotent consumer.
- **Field reading:** *Interviews Vol IV* ch. 06–07 (fan-out, throughput), *Architecture Decision Playbook* D01 + D03, *System Design Reality* ch. 4–5.
- **Design doc prompt:** "Monolith or microservices for a 12-engineer startup shipping a marketplace? Write the decision memo both ways."

### Part V — Practice

#### M08 · Case Study Lab (Weeks 10–11)

**Goal:** see every concept from Parts I–IV surviving contact with production.

Work the 35 case studies in 8 themed sprints (full catalog in §4). Per case: 20-minute skim → redraw the architecture from memory → write two lines: *one decision you'd copy, one trade-off you'd question*.

#### M09 · Design Workshop & Capstone (Week 12)

**Goal:** perform under pressure, and ship one thing you built end-to-end.

**The 45-minute runbook** (synthesized from the field library — memorize the shape, fill it with anything):

| Clock | Phase | What you do | The losing move |
|---|---|---|---|
| 0:00–0:05 | **Scope** | The 90-second opening, four moves: reframe ("Before I draw anything, I want to make sure I'm solving the right problem"), exactly three questions — **scale**, **axis** (read-heavy / write-heavy / latency-critical / durability-critical), **scope** ("what's explicitly out of scope?" — the magic one) — then name your sequence and invite redirection. Write scope in a corner and refer back to it ≥3 times. | Picking up the marker at second 12 |
| 0:05–0:10 | **Estimate** | Derive four numbers aloud in order: DAU → QPS → storage → bandwidth. "Assuming X and assuming Y, that puts us around Z." State the peak multiplier. | Declaring numbers with no chain underneath |
| 0:10–0:25 | **The spine** | One clean request→response path, the simplest thing that works. Then name the first bottleneck *before* going deep: "Given [number], the first thing that breaks is [X], because [fundamental limit]." | Adding cache, queue, and six services before anything demands them |
| 0:25–0:40 | **Deep dive** | Pick by three filters: where senior trade-offs live, where capacity numbers bite, where the interviewer's axis points. Seven steps: why this component → internals → alternatives → happy path → three failure modes → operations at 3 a.m. → "deeper, or move on?" | Going deep on a commodity component |
| 0:40–0:45 | **Name what breaks + defend** | Volunteer the weakness first: "The bottleneck here is X. At 10× scale, Y breaks first. If I had more time I'd shard Z." Answer every "why this?" with the four-part sentence below. | Presenting the design as failure-free |

**The four-part trade-off sentence** (the move that wins the deep phase): *"[Choice] because [reason], not [alternative] because [its cost], accepting [this choice's cost]."* — e.g. "Kafka, because we need replay at this volume. If it were low-volume with complex routing, I'd use RabbitMQ. The replay requirement is what decides it."

**The scale jump** (minute ~32, it's a reset, not a continuation): never "add more servers." Name the qualitative shifts — geographic distribution (50–150 ms cross-region floor), multi-layer caching (each layer its own invalidation story), async everywhere, distributed data — and the staff-level fifth: **at 1× the bottleneck is compute; at 100× the bottleneck is coordination.**

**Pushback protocol:** "You're right to push on that — let me redo it" is a reset, not a defeat. Pivot, don't restart: keep the board, fix the pushed piece. Defend only ~1 in 10 pushbacks, anchored to a specific constraint or number. The interviewer is grading adaptability, not the revised architecture.

**The eight fatal mistakes** (self-audit before every mock): designing before scoping · demonstrating knowledge instead of judgment · covering everything at shallow depth · skipping capacity math · single points of failure · no trade-off talk · ignoring security · no observability story.

- **Drills:** *Interviews Vol IV* (10 chapters = 10 drills), *Interview Cheatsheet* (framework, mistakes, 4 worked patterns: feed fan-out hybrid, URL shortener, chat, search), *Survival Kit* (opening + checklist), *45-Minute Map*, *Visual Atlas* §01 (the interview, drawn).
- **Capstone** (via *Build Your Own X*): a Raft-based KV store with leader election · a message queue with delivery guarantees · a load balancer · a rate limiter · a URL shortener with a full design doc. Defend every major capstone decision with the four-part sentence.
- **Interview prep layer:** work through *Tech Interview Handbook* and *Coding Interview University* in parallel from Week 8, not Week 12.

### Part VI — The Field Manual

#### M10 · Production Operations (Weeks 13–14)

**Goal:** run what you design — incidents, reviews, and the written record.

**A. The first ten minutes of an incident.** One rule: **read before you write** — every diagnostic step is read-only until the failure is classified; "you cannot make an incident worse by looking." Work the order: **Classify → Confirm → Narrow → Mitigate → Verify.** Three search-space-cutting questions: *What changed?* (most incidents are something that changed in the last hour, not a spontaneous failure) · *How wide?* (endpoint / service / region / everything) · *Is it accelerating?* (accelerating means mitigate now, diagnose later). Confirm with numbers, not vibes: check the dependency's own metrics, not your latency to it; correlate the start time to a change, to the minute. Mitigate with reversible moves, **one change at a time** — three changes plus recovery teaches you nothing. And respect the capacity trap: adding instances makes retry storms, stampedes, and leaks *worse*.

**B. The seven failure shapes** (recognize the shape, don't memorize incidents):

| Shape | Signature | First check |
|---|---|---|
| Connection pool exhaustion | Everything slow, DB idle | Pool utilization / acquire-wait — not query time |
| Retry storm | Load far above real traffic, no deploy behind it | Caller retry / backoff config |
| Cache stampede | DB fine, then dead instantly at peak | A shared expiry timestamp |
| Resource leak | Slow climb for hours or days, then a wall | The trend, not one snapshot |
| Swallowed exception | Logs say success, users see failure | Catch blocks near the failure |
| Deadlock / lock contention | Everyone waiting, no one working | Lock order, not lock count |
| "Everything is green" | Dashboards fine, users blocked | One real user path, end to end |

**C. Case study — The 02:43 Outage** (read the full postmortem, then debrief): payments P99 climbs 280 ms → 4.2 s; the connection pool saturates; every DB dashboard looks healthy. 35 minutes go missing in the wrong layer (EXPLAIN ANALYZE: all queries <2 ms; zero blocking locks) — until the senior's one question: *"What are the ten connections actually doing right now?"* Answer: 8 of 10 connections `idle in transaction`, `wait_event_type = Client` — the app, not the DB, holds them. Root cause: a synchronous fraud-API HTTP call inside `@Transactional` — ~55 ms of DB work holding each connection ~8 s while the third party degraded; a **31× throughput collapse**. The fix is three structural lines (move the call before the transaction); the hardening is an audit of all 16 transactional methods, a circuit breaker, and a 30 s → 10 s acquisition timeout. The rule it teaches: **transaction duration equals the duration of the slowest synchronous thing inside it.** And the meta-lesson: the same shape was diagnosed in 4h12m, then 1h47m, 38m, 11m, 7m, 4m, 2m, and finally 90 seconds — pattern recognition is exposure, compressed.

**D. Code review as an incident filter.** The senior question: *"What would have to be true for this to break in production six months from now?"* Twenty patterns across eight families — correctness slips (unreachable returns, wrong default branches), concurrency (read-modify-write races, unsafe lazy singletons), database anti-patterns (N+1 hidden behind getters, missing index without `CREATE INDEX CONCURRENTLY`, transactions held across HTTP calls), API contract drift (breaking renames, optional → required), reliability omissions (HTTP clients without timeouts, retries without idempotency keys, sync calls on the critical path), security slips (log injection, IDOR / tenant scoping from request bodies), test theater (assertions generated from the buggy output, mocks that test themselves). Reviewer discipline: 0–3 load-bearing comments per PR; block for data loss, security, breaking APIs, and migration order; approve-with-concerns for the rest; **bring data, not taste.**

**E. Writing it down.** The ADR, six sections: decision-statement title, status, context (≤2 paragraphs), decision, alternatives considered (the section lazy authors cut and future readers most need), consequences — readable in five minutes, in version control next to the code. The postmortem: blameless means actions, not actors ("the deployment was approved at 14:32"); **max 3 action items**, each with a named owner and date; review the corpus quarterly and invest in the recurring category.

- **Labs:** run the 7-shape triage against the 02:43 timeline and write its postmortem; review a seeded PR and leave exactly three load-bearing comments; write the ADR for your M03 sharding decision.
- **Field reading:** *Production Incident Field Card*, *The 02:43 Outage*, *Code Review Playbook*, *Decision Map* D1–D6 + D12–D15 (rollback default rule, OOMKilled causes, load average ≠ CPU utilization, the AI-inference-in-production trap), *Staff Engineers Architecture Playbook* Part IV.
- **Design doc prompt:** "Make the fraud-check pattern impossible: what changes at the code, review, and runtime layers?"

#### M11 · The Senior Track (Week 15)

**Goal:** judgment, made visible — decisions, communication, and the offer.

**A. The decision framework.** Before any architecture decision, four questions: *Is this reversible? What is the blast radius? What does it cost to not decide? What does it constrain downstream?* Two-way doors vs one-way doors; the asymmetry rule (irreversible + wide blast radius deserves ~10× the deliberation). Five cost dimensions — infrastructure is the only one on the slide, and rarely the largest: engineering time, operational tax ("who is on call for this in three years?"), cognitive load, opportunity cost. *"Most bad architecture decisions are not made deliberately. They are made by default."*

**B. Eight decisions as drills** — each with the rule that settles it and the loss case that proves it:

| Decision | The rule that settles it | The loss case |
|---|---|---|
| Kafka vs RabbitMQ | Throughput / replay / ordering / ops — under ~5K msg/s the choice doesn't differentiate; replay needs a log | 500 emails/min on a 3-broker Kafka cluster: ~10× the cost of RabbitMQ |
| PostgreSQL vs DynamoDB | Access-pattern predictability decides; Postgres is the default until proven otherwise; after 3–4 GSIs "you are operating five tables" | 200 req/s SaaS "for web scale": 5 GSIs by month 9, 4-month migration back to Postgres |
| Monolith vs microservices | Team topology first (Conway); <25 engineers ≈ almost always a mistake; modular monolith keeps the door open | 12 engineers, 12 services: every feature touched 3+, 8 merged back, ~2 engineer-years lost |
| Consistency per operation | Strong for money, inventory, uniqueness; eventual for feeds and dashboards; read-after-write is its own requirement | Eventually-consistent inventory cache oversold 4,000 units in a flash sale |
| REST / gRPC / GraphQL | By consumer profile; most systems need one style, a few need two, almost nothing needs three | Three API styles over one data model: drift, tripled on-call, 2 of 3 deprecated |
| Sync vs async | Latency budget + failure cost + idempotency decide; async-by-default for anything the user doesn't wait on | Payment auth made async: silent failures, 2 months of reconciliation infra |
| Replicas vs sharding | >80% reads → replicas (reversible); >30% writes → sharding (effectively irreversible); analyze hot keys first | Sharded at 8K writes/s, 95% reads: ~1 engineer-year round trip for no benefit |
| Build vs buy | Core → build; context → buy; critical-but-not-core → deliberate, time-boxed, with documented exit criteria | Feature flags built because "the vendor was too expensive": ~1 engineer-year wasted |

**C. Communication — the radius of thinking.** What committees actually measure is how far the consequences of your decisions traveled: **team → org → company** (the scope ladder). The highest-leverage sentence: *"We considered [X], and chose not to, because [constraint] mattered more than [what X would have given us]."* Impact formula: **reach × severity × business value** — and if you lack the number, show the estimation method instead of inventing one. Phrase swaps: "I built X" → "I chose X over Y, because Z mattered more"; "It went well" → "It hit [metric] against a baseline of [metric]"; "I escalated it" → a documented last resort, taken with data. The eight failure patterns to self-audit against: too technical · no system thinking · escalated as first move · can't quantify · process without outcome · no trade-offs named · no mentorship signal · no story about being wrong.

**D. The offer.** Level is the biggest lever — negotiate the level before the number. Scope and ownership over title. The real money moves in equity and sign-on, not base; competing offers in writing are the whole game. Never accept on the call — *"the relief is the expensive emotion."* Compensation signals, weak vs strong: writes the most code → reduces the need for code; says yes to everything → says no, with a reason; knows the most tools → knows which tool not to use.

- **Labs:** run three decision-matrix drills aloud (pick any three rows above); rewrite two of your own project stories through the scope ladder and phrase swaps; run the capstone defense — every major decision answered with the four questions plus the trade-off sentence.
- **Field reading:** *Backend Architecture Decision Playbook* (all 8 decisions), *Senior Backend Decision Map* (20 junior/senior defaults), *Staff Engineers Architecture Playbook* (Part I–III: framework + case studies), *Staff Engineer Communication Playbook*, *Staff Engineer Interview Playbook*, *What the $250K Engineer Knows*, *Decision Cards*, *Senior Backend Field Cards*.
- **Design doc prompt:** "The decision record of your capstone: one ADR per major choice, each with the alternative you rejected and the cost you accepted."

---

## 4. Case study catalog — 35 architectures in 8 themes

| # | Theme | Cases | Reinforces |
|---|---|---|---|
| 1 | **Real-Time & Messaging** | Discord (Trillion Message Indexing) · Twilio (Exactly-Once Delivery) · Slack (Cellular Architecture Migration) · Netflix (Distributed Tracing Infrastructure) | M04 consistency, M06 idempotency, M07 queues, observability |
| 2 | **Storage & Data Infrastructure** | Dropbox (Magic Pocket) · GitHub (Distributed Storage System) · Airbnb (Key-Value Architecture) · Datadog (Husky Event Store) | M03 storage/sharding, M04 consistency, M07 queues |
| 3 | **Edge & Global Scale** | Cloudflare (Global Edge Architecture) · Pinterest (Cache Infrastructure Scaling) · eBay (Distributed Listing) · Walmart (Autocomplete Backend Rebuild) | M02 CDN/load balancing, M05 caching, M03 partitioning |
| 4 | **Payments & Financial Reliability** | Stripe (Database Migration Platform) · PayPal (Kafka Scaling) · Razorpay (Reliable Dual Writes) · Coinbase (Solana Processing) · PhonePe (Distributed Job Scheduler) · Capital One (Resilient Systems) | M04 transactions/outbox, M06 idempotency & resilience, M07 queues |
| 5 | **Migration Journeys** | Shopify (Sharded Monolith) · DoorDash (Microservices Migration) · Zomato (Billing Platform Scaling) | M03 sharding, M07 monolith↔microservices, M06 fault tolerance |
| 6 | **Event-Driven Architectures** | AWS (Event-Driven Architecture) · Meta (Distributed Priority Queue) · Salesforce (Guaranteed Data Delivery) · Canva (Analytics Event Pipeline) · Etsy (Kafka Zonal Resiliency) | M07 queues/event-driven, M06 fault tolerance |
| 7 | **Platform Engineering & Internal Infrastructure** | Google (System Design Principles) · Microsoft (Platform Engineering Paths) · Atlassian (Cloud Engineering) · Expedia (Configuration Management Platform) · Adobe (Unified Search Architecture) | M02 API gateway, M07 service discovery, organizational design |
| 8 | **Consumer Apps at Scale** | Uber (Rider App Architecture) · Spotify (Backend Infrastructure) · Figma (Multi-Database Scaling) · Instacart (Multi-Database Scaling) | M03 database scaling, M05 caching, M02 request path |

Reading order note: Theme 1–4 map directly onto Parts II–III; read those first, then 5–8.

---

## 5. The 15-week schedule

| Week | Focus | Deliverable |
|---|---|---|
| 1 | M01 Scaling fundamentals | Estimation drill sheet + 50M-DAU messenger estimate |
| 2 | M02 Request path | Token-bucket rate limiter + full request-path diagram |
| 3 | M03 Database scaling & replication | Read replica setup notes + failover walkthrough |
| 4 | M03 Sharding & partitioning | Consistent-hashing KV store (lab) |
| 5 | M04 Consistency & transactions | Saga lab + consistency-model cheat sheet |
| 6 | M05 Caching | Cache-aside lab with hit-rate measurements + stampede fix |
| 7 | M06 Resilience | Circuit-breaker lab + payment-API resilience doc |
| 8 | M07 Queues & event-driven | Mini message queue with delivery guarantees |
| 9 | M07 Microservices & coordination | Monolith-vs-microservices decision memo + Raft reading |
| 10 | M08 Case sprint A | Teardowns: Themes 1–4 (18 cases) |
| 11 | M08 Case sprint B | Teardowns: Themes 5–8 (17 cases) |
| 12 | M09 Capstone + mock interviews | Capstone repo + two timed mock designs |
| 13 | M10 Incident response | 7-shape triage run against the 02:43 timeline + postmortem draft |
| 14 | M10 Code review & written record | 3-comment review lab + capstone ADR |
| 15 | M11 The senior track | Decision drills + capstone defense (four questions + trade-off sentences) |

---

## 6. Core reading libraries (the 10 source repos)

| Library | Role in this course |
|---|---|
| System Design Academy | Core curriculum text for Parts I–IV |
| Developer Roadmaps | Track progress; place yourself on the backend map |
| Tech Interview Handbook | Interview layer for M09 |
| Coding Interview University | CS-fundamentals refresher behind every module |
| Build Your Own X | Source of every lab and the capstone |
| Engineering Leadership | Context for Part IV org-level trade-offs |
| Path to Senior Engineer Handbook | Leveling context: why senior engineers think in trade-offs |
| freeCodeCamp | Prerequisite refresh (networking, databases, APIs) |
| Public APIs | Real data sources for capstone projects |
| Free Programming Books | Deep reference reading (DDIA and friends) |

The original curated list circulates with shortened `lnkd.in` links; the full list is preserved verbatim in the appendix below.

---

## 7. The field document library (17 volumes)

A second layer of course material: interview runbooks, decision playbooks, incident postmortems, and code-review patterns. The ProdRescue volumes are by Devrim Özcay; the library was provided with the course material.

| # | Document | Type | What it gives the course |
|---|---|---|---|
| 1 | The 45-Minute Map | Interview runbook | The time-boxed shape of the design round (M09) |
| 2 | System Design Interview Cheatsheet | Cheatsheet | 80/20 framework, the 8 fatal mistakes, capacity formulas, 4 worked patterns (M01, M09) |
| 3 | System Design Interview Survival Kit | Survival guide | The 90-second opening, 5 rejection patterns, prompt-pattern table, round checklist (M09) |
| 4 | System Design Interviews Vol IV | Drill book | 10 drills: opening, capacity, depth vs breadth, trade-off naming, bottleneck-first, fan-out, throughput, consistency under partition, scale jump, pushback (M01, M04, M09) |
| 5 | System Design Visual Atlas | Visual atlas | 36 reference diagrams, one per pattern — the picture for each lesson (all modules) |
| 6 | The Backend Architecture Decision Playbook | Decision playbook | 8 fully-decoded decisions with matrices, win/loss cases, anti-patterns (M03, M04, M07, M11) |
| 7 | The Senior Backend Decision Map | Decision map | 20 junior-path vs senior-path default behaviors, from 2 a.m. incidents to staff interviews (M10, M11) |
| 8 | Staff Engineers Architecture Playbook | Architecture playbook | The four-question decision framework, reversibility/blast-radius maps, five cost dimensions, 4 production case studies, ADR + postmortem templates (M10, M11) |
| 9 | The Staff Engineer Communication Playbook | Communication playbook | The radius of thinking, scope ladder, trade-off sentence, phrase swaps, 8 failure patterns (M11) |
| 10 | Staff Engineer Interview Playbook | Interview playbook | Staff-level answer patterns, impact formula, 4 failure patterns, 5 real Q&As (M11) |
| 11 | What The $250K Engineer Knows | Career guide | 8 judgment moments where compensation actually moves (M11) |
| 12 | Senior Engineer Decision Cards | Field cards | Pocket cards: the first ten minutes, the 45-minute clock, before you sign (M09, M10, M11) |
| 13 | Senior Backend Field Cards | Field cards | Pocket procedures for the 2 a.m. incident, the design interview, and the offer (M10, M11) |
| 14 | Production Incident Field Card | Field card | The 10-minute triage order and 7 failure shapes (M10) |
| 15 | The 02:43 Outage | Incident case study | Full narrated postmortem: connection-pool exhaustion via an external call inside a transaction (M10) |
| 16 | Code Review Playbook | Playbook | 20 review patterns across 8 families + reviewer judgment (M10) |
| 17 | 09 System Design Reality | Scaling essay | The 1K → 10M user evolution: what actually breaks at each phase (M01, M02, M03, M05, M07) |

---

## Appendix · Source links, verbatim from the material

**Learning libraries (10):**

1. System design academy — https://lnkd.in/eKATU6QV
2. Public APIs — https://lnkd.in/epWSyzqs
3. Tech interview handbook — https://lnkd.in/e7EjsJNF
4. Coding interview university — https://lnkd.in/evJSNCPE
5. Engineering leadership — https://lnkd.in/ePCzV3zF
6. Freecodecamp — https://lnkd.in/e_4pA8xV
7. Developer roadmaps — https://lnkd.in/e9MuB_Yg
8. Path to senior engineer handbook — https://lnkd.in/exkJCxVi
9. Free programming books — https://lnkd.in/eXAzAJ3M
10. Build your own x — https://lnkd.in/ekZQbTPz

**System design concepts (23):**

1. Load Balancing — https://lnkd.in/gH9rdjCx
2. CDN — https://lnkd.in/g83A7-rM
3. Caching — https://lnkd.in/gTjxhv2V
4. Cache Invalidation — https://lnkd.in/geC955AY
5. Rate Limiting — https://lnkd.in/gWqJzCNJ
6. API Gateway — https://lnkd.in/gBNKpecH
7. CAP Theorem — https://lnkd.in/g4yFYkEi
8. Sharding — https://lnkd.in/gFi23iNV
9. Replication — https://lnkd.in/gikkrmNp
10. Partitioning — https://lnkd.in/gQhJS8ii
11. Queues — https://lnkd.in/gPGiuxtu
12. Microservices — https://lnkd.in/gZfYV2Qu
13. Microservices Vs Monoliths — https://lnkd.in/gM-dKE3D
14. Fault Tolerance — https://lnkd.in/gdamMmtc
15. Database Scaling — https://lnkd.in/ghq4v_gQ
16. Service Discovery — https://lnkd.in/gjfbNVBe
17. Consistency models — https://lnkd.in/gGkMENA3
18. Eventual Consistency — https://lnkd.in/gdSn54SK
19. Distributed Transactions — https://lnkd.in/gTc8pSbH
20. Leader Election — https://lnkd.in/g-kwhzSb
21. Horizontal vs Vertical Scaling — https://lnkd.in/gW-Vi9Qt
22. Back of the Envelope Estimation — https://lnkd.in/gQ6vtM3U
23. Idempotency, Data Latency & Finale — https://lnkd.in/gapgNSgh

**Company architecture case studies (35):**

1. Google System Design Principles — https://lnkd.in/gPKFwSYD
2. Meta Distributed Priority Queue — https://lnkd.in/gBBr4Vjq
3. Microsoft Platform Engineering Paths — https://lnkd.in/gymvyfbd
4. Adobe Unified Search Architecture — https://lnkd.in/g_SNVuzE
5. Salesforce Guaranteed Data Delivery — https://lnkd.in/gxCVtXZu
6. AWS Event Driven Architecture — https://lnkd.in/gT463eWY
7. Netflix Distributed Tracing Infrastructure — https://lnkd.in/gESgRhWU
8. Uber Rider App Architecture — https://lnkd.in/gGbxqbpU
9. Airbnb Key Value Architecture — https://lnkd.in/gqTSagR4
10. Dropbox Magic Pocket Architecture — https://lnkd.in/gfdfk7FV
11. Pinterest Cache Infrastructure Scaling — https://lnkd.in/g3NZnxAm
12. Slack Cellular Architecture Migration — https://lnkd.in/gtnkNEzF
13. Spotify Backend Infrastructure Architecture — https://lnkd.in/gCebV4sR
14. Cloudflare Global Edge Architecture — https://lnkd.in/gfAq7JTH
15. Stripe Database Migration Platform — https://lnkd.in/gVvP7VWQ
16. Shopify Sharded Monolith Changes — https://lnkd.in/g_KZ-BA4
17. DoorDash Microservices Migration Journey — https://lnkd.in/gBC5E3g2
18. Discord Trillion Message Indexing — https://lnkd.in/gRkk_d9G
19. Twilio Exactly Once Delivery — https://lnkd.in/ga7Zfank
20. Datadog Husky Event Store — https://lnkd.in/gWcZgw3S
21. Atlassian Cloud Engineering Architecture — https://lnkd.in/gyaGJxHY
22. PayPal Kafka Scaling Architecture — https://lnkd.in/gBRT8R-P
23. eBay Distributed Listing Architecture — https://lnkd.in/gqUVQRiW
24. Walmart Autocomplete Backend Rebuild — https://lnkd.in/gbVKZT2p
25. Capital One Resilient Systems — https://lnkd.in/gSv385XX
26. Canva Analytics Event Pipeline — https://lnkd.in/gReCsAkW
27. Figma Multi Database Scaling — https://lnkd.in/gQqayzyk
28. Razorpay Reliable Dual Writes — https://lnkd.in/gRiV9ypn
29. PhonePe Distributed Job Scheduler — https://lnkd.in/gZ4ZVDkN
30. Zomato Billing Platform Scaling — https://lnkd.in/g9kcikQy
31. Coinbase Solana Processing Architecture — https://lnkd.in/gyYwXm8g
32. Etsy Kafka Zonal Resiliency — https://lnkd.in/gJcnfTer
33. Expedia Configuration Management Platform — https://lnkd.in/gkj5GerG
34. Instacart Multi Database Scaling — https://lnkd.in/gUfawb2B
35. GitHub Distributed Storage System — https://lnkd.in/gDAAq6RP
