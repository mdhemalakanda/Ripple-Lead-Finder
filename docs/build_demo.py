#!/usr/bin/env python3
"""
Build docs/index.html — a fully static demo of the dashboard for GitHub Pages.

Reads ../dashboard.html, injects a fetch shim that answers every /api/* call
with deterministic sample data (no live OpenStreetMap traffic, no backend),
and writes the result to docs/index.html. Run from the repo root:

    python3 docs/build_demo.py

Re-run after every dashboard.html change so the demo stays in sync.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "dashboard.html"
OUT = pathlib.Path(__file__).resolve().parent / "index.html"

BANNER = """
<div style="background:#2f4a3c;color:#eaf4ee;padding:9px 18px;font-size:12.5px;text-align:center;font-family:inherit">
  <b>Static demo</b> — sample data only. The real app searches OpenStreetMap live and runs
  locally: <a href="https://github.com/RippleCheck/Ripple-Lead-Finder" style="color:#bfe3cf">get it here</a>.
</div>
"""

SHIM = """
<script>
// ── DEMO SHIM: answers every /api/* call with deterministic sample data so the
// dashboard runs unmodified on GitHub Pages. No network requests leave the page.
(function () {
  const realFetch = window.fetch.bind(window);

  const NICHES = ["Car Wash", "Barber Shop", "Dental Clinic", "Estate Agent", "Cafe",
    "Gym", "Restaurant", "Plumber", "Electrician", "Hair Salon", "Auto Repair",
    "Bakery", "Florist", "Photographer", "Dog Groomer", "Yoga Studio"];

  const CITIES = ["London", "Manchester", "Birmingham", "Leeds", "Glasgow", "Liverpool",
    "Bristol", "Sheffield", "Edinburgh", "Cardiff", "New York", "Los Angeles", "Chicago",
    "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego", "Dallas", "Austin"];

  const FIRST = ["Sunrise", "Golden", "Riverside", "Central", "Elite", "Fresh", "Prime",
    "Silver", "Crown", "Metro", "Harbour", "Maple", "Oakwood", "Bluebird", "Star"];
  const SECOND = ["& Co", "Hub", "Point", "Centre", "Studio", "House", "Works", "Room",
    "Group", "Express", "Lounge", "Bar"];

  const mod = (i, m, s) => (i * 7919 + s * 104729) % m;

  function mkLeads(niche, place, count, startId) {
    const parts = (place || "London, United Kingdom").split(",");
    const city = parts[0].trim();
    const country = (parts[1] || "United Kingdom").trim();
    const out = [];
    for (let i = 0; i < count; i++) {
      const noSite = i % 3 !== 0;
      const n = mod(i, 900, 3);
      out.push({
        id: startId + i,
        name: FIRST[mod(i, FIRST.length, 1)] + " " + niche + " " + SECOND[mod(i, SECOND.length, 2)],
        niche: niche, city: city, country: country,
        address: (mod(i, 90, 4) + 10) + " High Street, " + city,
        phone: noSite || i % 2 ? "+44 7" + String(100000000 + n * 977).slice(0, 9) : "",
        phone_e164: noSite || i % 2 ? "+447" + String(100000000 + n * 977).slice(0, 9) : "",
        email: i % 2 === 0 ? "info@" + FIRST[mod(i, FIRST.length, 1)].toLowerCase().replace(/\\s/g, "") + n + ".example.com" : "",
        website: noSite ? "" : "http://old-site-" + n + ".example.com",
        socials: {}, links_ok: {},
        opening_hours: "", lat: null, lon: null, osm_url: "",
        reason: noSite ? "No website tag on OpenStreetMap" : "Website unreachable",
        score: 55 + mod(i, 40, 6),
        reachability: "", owner: "", verified_date: "2026-10-28",
        whatsapp: false, activity: "", segment: "",
        stage: ["New", "New", "Contacted", "New", "Replied"][i % 5],
        starred: i === 1, notes: "",
        found_at: "2026-10-28"
      });
    }
    return out;
  }

  // the demo "database"
  let DB = mkLeads("Car Wash", "Los Angeles, United States", 8, 1);
  let nextId = 1000;

  const J = (obj) => new Response(JSON.stringify(obj), { headers: { "Content-Type": "application/json" } });

  function facets() {
    const uniq = (k) => Array.from(new Set(DB.map(l => l[k]).filter(Boolean))).sort();
    return { niches: uniq("niche"), countries: uniq("country"), cities: uniq("city") };
  }

  function leadList(params) {
    let rows = DB.slice();
    const eq = (k, v) => { if (v) rows = rows.filter(l => l[k] === v); };
    eq("niche", params.get("niche")); eq("country", params.get("country"));
    eq("city", params.get("city")); eq("stage", params.get("stage"));
    if (params.get("starred")) rows = rows.filter(l => l.starred);
    const q = params.get("q");
    if (q) rows = rows.filter(l => (l.name + " " + l.city).toLowerCase().includes(q.toLowerCase()));
    rows.sort((a, b) => (b.starred - a.starred) || (b.score - a.score) || a.name.localeCompare(b.name));
    const stages = {};
    rows.forEach(l => { stages[l.stage] = (stages[l.stage] || 0) + 1; });
    return {
      leads: rows, stages: stages,
      starred_total: rows.filter(l => l.starred).length,
      total_all: DB.length, facets: facets()
    };
  }

  window.fetch = async function (input, init) {
    const url = typeof input === "string" ? input : (input && input.url) || "";
    const method = ((init && init.method) || (input && input.method) || "GET").toUpperCase();
    let body = {};
    try { body = init && init.body ? JSON.parse(init.body) : {}; } catch (e) {}
    const u = new URL(url, location.origin);
    const p = u.pathname;

    if (!p.startsWith("/api/")) return realFetch(input, init);

    // small delay so spinners and progress messages behave like the real app
    await new Promise(r => setTimeout(r, p === "/api/search" ? 1200 : 120));

    if (p === "/api/niches") return J({ has_openai: false, lang: "en", niches: NICHES, segments: {} });
    if (p === "/api/cities") return J({ cities: CITIES, source: "demo" });
    if (p === "/api/health") return J({ ok: true });
    if (p === "/api/settings") return J({});
    if (p === "/api/brief")
      return J({ brief: "Demo mode — the real app builds this brief from live map data and the business's current website.", source: "demo" });
    if (p === "/api/message")
      return J({ message: "Demo mode — the real app writes a personalised outreach message for this business.", source: "demo" });
    if (p === "/api/manual-link")
      return J({ error: "Demo mode — manual link building needs the local app." });

    if (p === "/api/search") {
      const niche = body.niche || "Car Wash";
      const place = body.place || "London, United Kingdom";
      const leads = mkLeads(niche, place, 7, nextId);
      leads.forEach(l => { if (!DB.some(x => x.name === l.name && x.city === l.city)) DB.push(l); });
      nextId += 100;
      const parts = place.split(",");
      return J({
        place: place,
        scanned: 40 + mod(place.length, 120, 5),
        found: leads.length, new_leads: leads.length, duplicates: 0,
        filter_niche: niche,
        filter_city: parts[0].trim(),
        filter_country: (parts[1] || "").trim(),
        whatsapp_count: 2, note: "Demo mode — these are sample businesses, not live map results.",
        leads: leads
      });
    }

    if (p === "/api/leads") return J(leadList(u.searchParams));

    const m = p.match(/^\\/api\\/lead\\/(\\d+)$/);
    if (m) {
      const id = +m[1];
      const lead = DB.find(l => l.id === id);
      if (!lead) return J({ error: "Lead not found" }), new Response(null, { status: 404 });
      if (method === "DELETE") { DB = DB.filter(l => l.id !== id); return J({ ok: true }); }
      ["stage", "notes", "phone", "email", "starred"].forEach(k => {
        if (body[k] !== undefined) lead[k] = body[k];
      });
      return J({ ok: true });
    }

    if (p === "/api/export.csv") {
      const head = "name,niche,city,country,phone,email,website,score,stage";
      const lines = DB.map(l => [l.name, l.niche, l.city, l.country, l.phone, l.email, l.website, l.score, l.stage]
        .map(v => '"' + String(v == null ? "" : v).replace(/"/g, '""') + '"').join(","));
      return new Response([head].concat(lines).join("\\n"), { headers: { "Content-Type": "text/csv" } });
    }

    return J({});
  };
})();
</script>
"""


def build() -> None:
    html = SRC.read_text(encoding="utf-8")

    for marker in ("DEMO SHIM", "Static demo</b>"):
        if marker in html:
            sys.exit("dashboard.html already contains demo markers — nothing to do")

    # banner right after <body>, fetch shim just before the main script block
    html = html.replace("<body>", "<body>" + BANNER, 1)
    idx = html.rindex("<script>")
    html = html[:idx] + SHIM + "\n" + html[idx:]

    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({len(html):,} bytes)")


if __name__ == "__main__":
    build()
