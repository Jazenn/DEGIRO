# Evaluation of 100% Free 24/7 Frontend & Hosting Architectures

**Target Application:** Personal DEGIRO Portfolio Tracking & Rebalancing Dashboard  
**Investigation Objective:** Identify a frontend architecture and hosting provider that guarantees a modern, clean, interactive UI, 100% free forever operation, and true 24/7 accessibility without cold sleep screens, long container spin-downs, or fragile Playwright/bot workarounds.

---

## Executive Summary & Final Verdict

| Architecture Option | Hosting Platform | Cold Start / Sleep Behavior | Visual Polish & Interactivity | 100% Free Forever Sustainability | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Serverless SPA (React / Svelte + Tailwind)** | **Cloudflare Pages** (or Vercel Hobby) | **0ms (Never sleeps)**; Edge CDN delivery | **Exceptional**; client-side reactivity, modern component libraries (shadcn, Tremor) | **Highest**; unmetered bandwidth on Cloudflare, no credit card required | **RECOMMENDED (Winner)** |
| **Streamlit** | Streamlit Community Cloud | **1–2 min cold start**; sleeps after 12h–7d, requires manual "Wake up" click | **Rigid / Low**; full script re-runs on interaction, brittle CSS injection | **Medium**; free tier exists but violates 24/7 requirement without human clicks | **REJECTED** |
| **Modern Python (NiceGUI / Reflex / FastHTML)** | Render Free / Hugging Face Spaces | **30–60s cold start**; Render spins down after 15 min; HF sleeps after 48h | **High (Reflex/NiceGUI)**; stateful WebSockets | **Low**; 750-hr cap on Render, Fly.io eliminated free tier, ephemeral containers | **REJECTED** |

### Definitive Recommendation
Adopt a **Serverless SPA architecture (Vite + React or SvelteKit with Tailwind CSS)** hosted on **Cloudflare Pages** (with optional Cloudflare Pages Functions) communicating with **Neon Serverless PostgreSQL** via `@neondatabase/serverless` (or Supabase via PostgREST). 

This setup delivers:
1. **Instant 0ms Page Loads:** Static assets are globally replicated across Cloudflare's Anycast edge network (300+ locations) and never sleep.
2. **True 24/7 Availability:** No "Zzzz" sleeping screens, no 60-second Render spin-up delays, and no need to maintain fragile cron ping bots.
3. **Sub-second Database Auto-Wake:** When Neon suspends compute (after 5 minutes of idle time), it wakes automatically on the very first incoming query in ~200–400ms without manual intervention or UI blockers.

---

## 1. Deep Dive: Serverless SPA on Edge CDN (Cloudflare Pages & Vercel)

### 1.1 Quotas, Bandwidth & Resource Limits

#### Cloudflare Pages
* **Bandwidth:** **Unlimited & Unmetered**. Cloudflare Pages does not meter or charge for static asset bandwidth on the free tier ([Cloudflare Documentation](https://developers.cloudflare.com/pages/platform/limits/)).
* **Pricing & Expiration:** $0 forever; no credit card required.
* **Asset Limits:** Up to 20,000 files per project; maximum single file size of 25 MiB.
* **Builds & Deployments:** 500 builds per calendar month, 1 concurrent build, unlimited preview deployments, unlimited custom domains.
* **Edge Functions (Cloudflare Pages Functions / Workers):** Shares the free Cloudflare Workers quota: **100,000 requests per day** across the account, 10ms CPU execution time per request, running on lightweight V8 isolates ([Cloudflare Workers Pricing](https://developers.cloudflare.com/workers/platform/pricing/)).

#### Vercel Hobby Tier
* **Bandwidth:** 100 GB Fast Data Transfer per month; 10 GB Fast Origin Transfer; 1,000,000 CDN requests per month ([Vercel Limits](https://vercel.com/docs/limits/overview)).
* **Serverless Functions:** 1,000,000 invocations per month; 360 GB-hours provisioned memory; 4 CPU-hours active compute. Maximum function duration is 300 seconds.
* **Terms:** Strictly restricted to personal, non-commercial use (which perfectly matches a personal DEGIRO tracker). Exceeding limits pauses the deployment until the monthly reset; no surprise bills.

### 1.2 Cold Start & Sleeping Behavior
* **Static Assets:** **0ms cold start.** Static bundles (HTML, CSS, JavaScript, WebAssembly) reside in edge memory/SSD caches across hundreds of points of presence worldwide. They **never sleep, never hibernate, and never spin down**.
* **Pages Functions / Edge Compute:** Cold start for V8 isolates is negligible (~0ms to 5ms), compared to hundreds of milliseconds on Node.js containers.

### 1.3 Database Communication (PostgreSQL Integration)
In a serverless SPA, traditional persistent TCP connection pooling (which can exhaust PostgreSQL connection limits) is replaced by edge-native drivers:

#### Option A: Neon Serverless PostgreSQL (Recommended)
* **Free Tier Allowance:** 0.5 GB – 1 GB storage, scale-to-zero compute ([Neon Pricing](https://neon.tech/pricing)).
* **Auto-Suspend:** Neon scales compute to zero after **5 minutes of inactivity**, preserving free compute hours.
* **Sub-Second Auto-Wake:** Unlike application containers, Neon compute intercepts incoming queries and wakes in **200ms–500ms**. There is **no user-facing sleep screen** and no manual action needed.
* **Connection Method:** Utilizes `@neondatabase/serverless` over HTTP (`neon()`) or WebSockets (`Pool`), eliminating connection exhaustion at the edge without requiring an external PgBouncer instance ([Neon Serverless Driver](https://neon.tech/docs/serverless/serverless-driver)).

#### Option B: Supabase (PostgREST API)
* **Free Tier Allowance:** 500 MB database, 50,000 monthly active users.
* **Connection Method:** Client-side `@supabase/supabase-js` or HTTP `fetch` querying PostgREST over HTTPS. PostgREST handles internal connection pooling and applies Row-Level Security (RLS) directly.
* **Inactivity Caveat:** Supabase free tier automatically **pauses after 7 days of inactivity** ([Supabase Docs](https://supabase.com/docs)). Waking up a paused Supabase project takes ~30 seconds or requires manually clicking in the dashboard (unless kept awake via a scheduled GitHub Action querying the PostgREST endpoint every 4 days).

---

## 2. Deep Dive: Streamlit on Streamlit Community Cloud

### 2.1 Free Tier Resource Limits
* **Compute & RAM:** Typically capped at **1 vCPU and ~1 GB RAM** (dynamically stretching to ~2.7 GB on occasion) ([Streamlit Community Cloud Limits](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app)).
* **Storage:** Ephemeral container storage. Large data processing or heavy in-memory dataframes easily crash with `Out of Memory (OOM)` errors.

### 2.2 Inactivity Sleep Policy & Wake-up Penalty
* **Hibernation Trigger:** Streamlit Community Cloud puts apps into hibernation after inactivity—often after **as little as 12 hours or up to 7 days without traffic**.
* **The "Zzzz" Sleep Screen:** The container is completely shut down and de-allocated. When a user visits the URL, they are greeted by an idling screen stating:  
  `"This app has gone to sleep due to inactivity. Yes, get this app back up!"`
* **Wake-up Delay:** Waking the app requires the user to click the button. Streamlit must clone the repository, run `pip install` across all dependencies, and re-execute the script, which takes **60 to 120 seconds**.
* **Anti-Idling Bots:** While automated pings (Playwright, Puppeteer, cron curls) are commonly attempted, Streamlit's platform frequently detects headless automated visits and fair-use policy violations, leading to suspended accounts.

### 2.3 Visual & Interactivity Bottlenecks
* **Execution Model:** Streamlit executes the **entire Python script from line 1 to the end** whenever an input widget (slider, date picker, tab) is toggled. Even with `@st.cache_data`, complex portfolio calculations introduce perceptible UI latency (200ms–1s).
* **Styling Constraints:** Layout customization is constrained to predefined widgets. Customizing CSS requires injecting raw `<style>` blocks via `st.markdown(..., unsafe_allow_html=True)`. This practice is fragile, breaks across Streamlit version upgrades, cannot support complex financial dashboard components (such as interactive candlestick zoom, multi-tier crypto scale ladders, or mobile drawer menus), and looks like an internal data science prototype rather than a polished product.

---

## 3. Deep Dive: Modern Python Alternatives on Free Containers

### 3.1 Framework Characteristics
* **NiceGUI:** High-level Python UI based on FastAPI, Vue.js, and Quasar. It relies on a continuous **bi-directional WebSocket connection** to synchronize DOM state. If the underlying server sleeps or restarts, the WebSocket disconnects and the UI freezes.
* **Reflex:** Compiles Python into a Next.js frontend with a FastAPI backend. Requires running both frontend asset serving and a Python backend event loop.
* **FastHTML:** Pure server-rendered hypermedia using Starlette, Uvicorn, and HTMX. Very lightweight and responsive, but still requires a continuously running Python ASGI web server.

### 3.2 Free Container Hosting Landscape

#### Render Free Web Services
* **15-Minute Spin-down:** Render automatically spins down free services after **15 minutes of zero inbound HTTP/WebSocket traffic** ([Render Free Tier Docs](https://render.com/docs/free)).
* **Cold Start Latency:** The subsequent incoming request triggers a cold start taking **30 to 60+ seconds**, during which Render serves an intermediate loading screen.
* **750 Free Hours Cap:** Workspaces receive 750 free instance hours per month. Running a service continuously 24/7 (31 days × 24 hours = 744 hours) exhausts the entire quota for all services in the account, leaving zero room for secondary services, background workers, or staging builds.

#### Fly.io
* **Status:** **Free tier discontinued.** In 2024, Fly.io ended its permanent free allowances for new users. New accounts receive only a 2-hour / 7-day trial before requiring a credit card and pay-as-you-go billing ([Fly.io Billing Docs](https://fly.io/docs/about/billing/)). It is no longer an option for 100% free hosting.

#### Hugging Face Spaces (CPU-Basic)
* **Inactivity Policy:** Free CPU-basic Spaces auto-sleep after **48 hours of complete inactivity** ([Hugging Face Spaces Docs](https://huggingface.co/docs/hub/spaces-overview)).
* **Cold Start:** Waking from sleep requires rebuilding or spinning up the Docker container, resulting in a **20 to 60-second delay**.

---

## 4. Multi-Dimensional Comparison Matrix

| Evaluation Dimension | Cloudflare Pages (Serverless SPA) | Vercel Hobby (Serverless Next.js/SPA) | Streamlit Community Cloud | Render Free (NiceGUI / FastHTML) | Hugging Face Spaces |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Edge CDN Cold Start** | **0ms (Instant)** | **0ms (Instant)** | N/A (Full container) | N/A (Full container) | N/A (Full container) |
| **Backend / DB Cold Start** | 200–500ms (Neon auto-wake) | 200–500ms (Neon) / ~250ms function | 60–120s (from cold sleep) | 30–60s (from 15m idle) | 20–60s (from 48h idle) |
| **Sleep / Idling Mechanism** | **Never sleeps** | **Never sleeps** | Sleeps after 12h–7d; displays "Zzzz" | Spins down after 15 minutes | Sleeps after 48 hours |
| **Manual Wake-up Required?** | **No** | **No** | **Yes (Manual click required)** | No (Waits 45s on request) | No (Waits 30s on request) |
| **Monthly Bandwidth Limit** | **Unlimited (Unmetered)** | 100 GB / month | Unspecified soft cap | 100 GB / month | Unspecified fair-use |
| **Monthly Compute Allowance**| 100k Function reqs/day | 1M Invocations / 360 GB-h | 1 app (1 CPU, 1GB RAM) | 750 hours/month | 1 Space (2 vCPU, 16GB) |
| **Visual Polish & Control** | Full CSS/Tailwind, shadcn, Tremor | Full CSS/Tailwind, shadcn, Tremor | Constrained; brittle `<style>` hacks | Good (Quasar / HTMX) | Constrained (Gradio/Streamlit) |
| **Client-Side Interactivity** | Instant (DOM / React state) | Instant (DOM / React state) | Slow (Full script re-run) | Fast (via WebSocket/HTMX) | Slow to medium |
| **Long-Term Sustainability** | Extremely high (Core CF product) | High (Personal hobby tier) | Medium (Subject to cloud policies) | Fragile (750h quota cliff) | Medium |

---

## 5. Implementation Architecture & Data Flow

To achieve 100% free, 24/7 reliability, zero cold sleep screens, and financial-grade polish:

```
[ Browser / Mobile Client ]
         │
         │ (1) 0ms Instant Load (Anycast Edge CDN)
         ▼
[ Cloudflare Pages: React/Svelte SPA + Tailwind CSS ]
         │
         │ (2) API Request via HTTP / WebSockets
         ▼
[ Cloudflare Pages Function (Edge Worker) OR Direct Client Fetch ]
         │
         │ (3) SQL over HTTP/WebSockets (@neondatabase/serverless)
         ▼
[ Neon Serverless PostgreSQL ]
   • Suspends after 5 min idle (0 CU consumed)
   • Transparently auto-wakes in ~300ms on incoming query
   • Zero manual wake-up screens or Playwright bots
```

### Key Engineering Benefits for DEGIRO Portfolio Tracker
1. **Financial Dashboard Polish:** Full support for `shadcn/ui`, `Tremor` (dashboard financial charts), `Recharts`, and `Tailwind CSS` enables interactive asset allocation donuts, crypto scale ladder visualizations, and real-time transaction filtering.
2. **Sub-second Perceived Latency:** While Neon wakes from scale-to-zero in ~300ms, the frontend SPA is already rendered with skeleton loaders in 0ms, providing an immediate, professional UX.
3. **Zero Maintenance & Zero Keep-Alive Overhead:** Eliminates background cron jobs, GitHub Actions pings, and Playwright headless scrapers that can fail or violate host terms of service.
4. **Resilient Free Tiers:** Cloudflare Pages' unmetered bandwidth combined with Neon's generous scale-to-zero compute ensures the personal dashboard will run indefinitely at zero cost.
