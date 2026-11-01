#!/usr/bin/env python3
"""
Build docs/index.html — a LIVE, fully client-side version of the dashboard
for GitHub Pages.

Reads ../dashboard.html and injects a fetch shim that reimplements the search
engine in JavaScript: geocoding (Nominatim -> Photon fallback), live Overpass
queries, the closed-shop filter, activity scoring and the no-website filter all
run directly in the visitor's browser against the same public APIs the desktop
app uses. Saved leads live in the browser's localStorage.

What deliberately still needs the desktop app:
  - website health checks ("Has a dead / bad website" mode) — browsers can't
    read third-party sites (CORS)
  - AI message rewrites — no API key on a static page
  - Foundry demo links — need the encryption keys

Run from the repo root after every dashboard.html change:

    python3 docs/build_demo.py
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import categories  # noqa: E402  (repo-local taxonomy)

OUT = pathlib.Path(__file__).resolve().parent / "index.html"

# name -> {seg, tags} for the whole catalogue
CATALOGUE = {
    name: {"seg": seg, "tags": [list(t) for t in tags]}
    for name, (seg, tags, _slug) in categories.CATALOGUE.items()
}

BANNER = """
<div style="background:#2f4a3c;color:#eaf4ee;padding:9px 18px;font-size:12.5px;text-align:center;font-family:inherit">
  <b>Live search</b> — this page queries OpenStreetMap directly from your browser; saved leads stay in this browser.
  Website health-checks, AI messages and Foundry links need the
  <a href="https://github.com/RippleCheck/Ripple-Lead-Finder" style="color:#bfe3cf">desktop app</a>.
</div>
"""

SHIM = """
<script>
// ── LIVE SHIM: reimplements the Flask API client-side so the dashboard runs
// unmodified on GitHub Pages, searching OpenStreetMap for real. ──────────────
(function () {
  const realFetch = window.fetch.bind(window);

  const CATALOGUE = __CATALOGUE__;

  const COUNTRY_ISO = {"United Kingdom":"GB","United States":"US","Australia":"AU","Canada":"CA","Ireland":"IE","New Zealand":"NZ","Germany":"DE","France":"FR","Spain":"ES","Italy":"IT","Netherlands":"NL","Belgium":"BE","Portugal":"PT","Austria":"AT","Switzerland":"CH","Sweden":"SE","Norway":"NO","Denmark":"DK","Finland":"FI","Iceland":"IS","Poland":"PL","Czechia":"CZ","Slovakia":"SK","Hungary":"HU","Romania":"RO","Bulgaria":"BG","Greece":"GR","Croatia":"HR","Slovenia":"SI","Serbia":"RS","Bosnia and Herzegovina":"BA","North Macedonia":"MK","Albania":"AL","Montenegro":"ME","Estonia":"EE","Latvia":"LV","Lithuania":"LT","Ukraine":"UA","Moldova":"MD","Georgia":"GE","Armenia":"AM","Azerbaijan":"AZ","Turkey":"TR","Cyprus":"CY","Malta":"MT","Luxembourg":"LU","Monaco":"MC","Andorra":"AD","United Arab Emirates":"AE","Saudi Arabia":"SA","Qatar":"QA","Kuwait":"KW","Bahrain":"BH","Oman":"OM","Jordan":"JO","Lebanon":"LB","Israel":"IL","Egypt":"EG","Morocco":"MA","Tunisia":"TN","Algeria":"DZ","South Africa":"ZA","Kenya":"KE","Nigeria":"NG","Ghana":"GH","Tanzania":"TZ","Uganda":"UG","Ethiopia":"ET","Rwanda":"RW","Botswana":"BW","Namibia":"NA","Zambia":"ZW","Zimbabwe":"ZW","Mauritius":"MU","Seychelles":"SC","Japan":"JP","South Korea":"KR","Singapore":"SG","Malaysia":"MY","Thailand":"TH","Vietnam":"VN","Philippines":"PH","Indonesia":"ID","Taiwan":"TW","Hong Kong":"HK","Sri Lanka":"LK","Nepal":"NP","Bangladesh":"BD","Pakistan":"PK","Kazakhstan":"KZ","Uzbekistan":"UZ","Mexico":"MX","Brazil":"BR","Argentina":"AR","Chile":"CL","Colombia":"CO","Peru":"PE","Ecuador":"EC","Uruguay":"UY","Paraguay":"PY","Bolivia":"BO","Costa Rica":"CR","Panama":"PA","Guatemala":"GT","Dominican Republic":"DO","Jamaica":"JM","Trinidad and Tobago":"TT","Bahamas":"BS","Barbados":"BB","Fiji":"FJ","Papua New Guinea":"PG"};

  // mobile-number detection per dialling code: prefixes, or full-length rule
  const MOBILE = {
    "44": { pre: ["7"] }, "1": { len: 10 }, "91": { pre: ["6","7","8","9"] },
    "61": { pre: ["4"] }, "64": { pre: ["2"] }, "353": { pre: ["8"] },
    "49": { pre: ["1"] }, "33": { pre: ["6","7"] }, "34": { pre: ["6","7"] },
    "39": { pre: ["3"] }, "31": { pre: ["6"] }, "971": { pre: ["5"] },
    "27": { pre: ["60","61","62","63","64","65","66","67","68","71","72","73","74","76","78","79","81","82","83","84"] }
  };
  const CC_BY_ISO = { gb:"44", us:"1", ca:"1", in:"91", au:"61", nz:"64", ie:"353", de:"49", fr:"33", es:"34", it:"39", nl:"31", ae:"971", za:"27", sg:"65", my:"60", pk:"92", bd:"880", lk:"94", np:"977", ph:"63", id:"62", th:"66", vn:"84" };

  const OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
  ];
  const NOMINATIM = "https://nominatim.openstreetmap.org/search";
  const PHOTON = "https://photon.komoot.io/api/";

  const THIN = new Set(["in","pk","bd","lk","np","ng","ke","id","ph","vn","th","eg","za"]);
  const CLOSED_MARKERS = ["disused","abandoned","demolished","razed","removed","closed","was","old","historic"];
  const CLOSED_NAME_HINTS = ["permanently closed","closed down","now closed","ceased trading","out of business","under new management","to let","for lease","coming soon","opening soon","site of former","former "];
  const SOCIAL_KEYS = { facebook:["contact:facebook","facebook"], instagram:["contact:instagram","instagram"], twitter:["contact:twitter","twitter"], whatsapp:["contact:whatsapp","whatsapp"] };

  const PRICE = { "United Kingdom":"£199", "United States":"$250", "Canada":"C$340", "Australia":"A$380", "New Zealand":"NZ$400", "Ireland":"€230", "Germany":"€230", "France":"€230", "Spain":"€230", "Italy":"€230", "Netherlands":"€230", "Portugal":"€230" };

  // ── helpers ──────────────────────────────────────────────────────────────
  const J = (obj, status) => new Response(JSON.stringify(obj), { status: status || 200, headers: { "Content-Type": "application/json" } });

  function phoneChannels(phone, iso) {
    if (!phone) return {};
    let raw = phone.replace(/[^\\d+]/g, "");
    if (!raw) return {};
    let digits = raw.startsWith("+") ? raw.slice(1) : raw.startsWith("00") ? raw.slice(2)
      : ((CC_BY_ISO[(iso || "").toLowerCase()] || "") + raw.replace(/^0+/, ""));
    const cc = Object.keys(MOBILE).sort((a, b) => b.length - a.length).find(c => digits.startsWith(c)) || "";
    const national = cc ? digits.slice(cc.length) : digits;
    const rule = MOBILE[cc];
    const isMobile = cc && national ? (rule.len ? national.length === rule.len
      : rule.pre.some(p => national.startsWith(p))) : null;
    return {
      e164: "+" + digits,
      whatsapp: isMobile !== false ? "https://wa.me/" + digits : ""
    };
  }

  function looksClosed(tags) {
    for (const key in tags) {
      if (key.includes(":") && CLOSED_MARKERS.includes(key.split(":")[0])) return true;
    }
    for (const f of ["disused","abandoned","closed","demolished","razed"])
      if (["yes","true","1"].includes(tags[f])) return true;
    if (["vacant","empty"].includes(tags.shop) || tags.office === "vacant") return true;
    if (tags.end_date || tags["demolished:building"]) return true;
    if (["ruins","ruin","collapsed"].includes(tags.building)) return true;
    if (tags.abandoned || tags.ruins === "yes") return true;
    const oh = (tags.opening_hours || "").trim().toLowerCase();
    if (["closed","off","no","none"].includes(oh)) return true;
    const name = (tags.name || "").toLowerCase();
    if (CLOSED_NAME_HINTS.some(h => name.includes(h))) return true;
    if (tags.construction || tags.proposed || tags.planned) return true;
    if (tags.building === "construction") return true;
    return false;
  }

  function activitySignals(tags, edited) {
    let n = 0;
    const oh = (tags.opening_hours || "").trim().toLowerCase();
    if (tags.opening_hours && !["closed","off"].includes(oh)) n++;
    if (tags.phone || tags["contact:phone"] || tags["contact:mobile"]) n++;
    if (Object.keys(tags).some(k => k.startsWith("contact:"))) n++;
    if (tags.check_date || tags["survey:date"]) n++;
    if (tags["addr:housenumber"] && tags["addr:street"]) n++;
    if (tags.wheelchair || tags["payment:cash"] || tags.cuisine || tags.outdoor_seating || tags.takeaway || tags.delivery) n++;
    if (edited && edited >= "2023-01") n++;
    return n;
  }

  function first(tags, keys) { for (const k of keys) { if (tags[k]) return String(tags[k]).trim(); } return ""; }

  function socialUrl(kind, val) {
    if (!val) return "";
    if (val.startsWith("http")) return val;
    const base = { facebook: "https://www.facebook.com/", instagram: "https://www.instagram.com/", twitter: "https://twitter.com/" }[kind] || "";
    return base ? base + val.replace(/^[@/]+/, "") : val;
  }

  function address(tags) {
    return [tags["addr:housenumber"], tags["addr:street"],
      tags["addr:city"] || tags["addr:town"] || tags["addr:suburb"] || "",
      tags["addr:postcode"]].filter(Boolean).join(" ").trim();
  }

  function mapsLinks(name, lat, lon, addr, city) {
    const out = {};
    if (lat == null || lon == null) {
      if (name) out.maps_verify = "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent([name, addr || city].filter(Boolean).join(" "));
      return out;
    }
    const ll = lat.toFixed(6) + "," + lon.toFixed(6);
    const label = [name, addr || city].filter(Boolean).join(" ");
    out.maps_verify = label ? "https://www.google.com/maps/search/" + encodeURIComponent(label) + "/@" + ll + ",18z"
      : "https://www.google.com/maps/search/?api=1&query=" + ll;
    out.maps_pin = "https://www.google.com/maps/search/?api=1&query=" + ll;
    out.maps_street = "https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=" + ll;
    return out;
  }

  function score(l) {
    let s = 0;
    if (l.phone) s += 40;
    if (l.email) s += 30;
    if (Object.keys(l.socials).length) s += 15;
    if (l.address) s += 5;
    if (l.opening_hours) s += 10;
    if (l.owner) s += 5;
    if (l.whatsapp) s += 20;
    s += Math.min(l.activity, 5) * 4;
    if (l.verified_date >= "2024-07") s += 10; else if (l.verified_date >= "2022-07") s += 5;
    return s;
  }

  function reachability(l) {
    if (l.whatsapp && l.email) return "WhatsApp + Email";
    if (l.whatsapp) return "WhatsApp";
    if (l.phone && l.email) return "Phone + Email";
    if (l.phone) return "Phone only";
    if (l.email) return "Email only";
    if (Object.keys(l.socials).length) return "Social only";
    return "Hard to reach";
  }

  // ── geocoding (Nominatim -> Photon, mirrors the desktop engine) ──────────
  async function geocode(place) {
    let geo = null;
    try {
      const r = await (await fetch(NOMINATIM + "?format=json&limit=1&addressdetails=1&q=" + encodeURIComponent(place))).json();
      if (r.length) {
        const a = r[0].address || {}, bb = r[0].boundingbox;
        if (bb && bb.length === 4) geo = {
          display_name: r[0].display_name, country: a.country || "",
          country_code: (a.country_code || "").toLowerCase(),
          bbox: [parseFloat(bb[0]), parseFloat(bb[2]), parseFloat(bb[1]), parseFloat(bb[3])],
          lat: parseFloat(r[0].lat), lon: parseFloat(r[0].lon)
        };
      }
    } catch (e) {}
    if (!geo) {
      const d = await (await fetch(PHOTON + "?limit=1&q=" + encodeURIComponent(place))).json();
      const f = (d.features || [])[0];
      if (!f) throw new Error("Couldn't find '" + place + "'. Try a more specific form like 'Leeds, United Kingdom'.");
      const p = f.properties || {};
      let south, west, north, east;
      if (p.extent && p.extent.length === 4) { west = p.extent[0]; north = p.extent[1]; east = p.extent[2]; south = p.extent[3]; }
      else { const [lo, la] = f.geometry.coordinates; south = la - 0.09; west = lo - 0.14; north = la + 0.09; east = lo + 0.14; }
      geo = {
        display_name: [p.name, p.state, p.country].filter(Boolean).join(", "),
        country: p.country || "", country_code: (p.countrycode || "").toLowerCase(),
        bbox: [south, west, north, east], lat: f.geometry.coordinates[1], lon: f.geometry.coordinates[0]
      };
    }
    return geo;
  }

  async function overpass(query) {
    let last = null;
    for (const mirror of OVERPASS) {
      try {
        const body = new URLSearchParams({ data: query });
        const r = await fetch(mirror, { method: "POST", body: body });
        if (!r.ok) throw new Error("HTTP " + r.status);
        const j = await r.json();
        // Some networks firewalls return a valid-but-empty {} for blocked
        // domains — treat that as a failure and try the next mirror.
        if (!j || !Array.isArray(j.elements)) throw new Error("empty/blocked response");
        return j;
      } catch (e) { last = e; }
    }
    throw new Error("OpenStreetMap's search API isn't reachable from this network right now " +
      "(all mirrors failed: " + last + "). If this keeps happening, your network may be blocking it — " +
      "try a different connection, or run the desktop app instead.");
  }

  // ── the search itself ────────────────────────────────────────────────────
  async function runSearch(body) {
    const niche = body.niche || "Barber Shop";
    const place = (body.place || "").trim();
    const mode = body.mode || "no_website";
    const limit = parseInt(body.limit) || 60;
    const strict = body.strict !== false;
    if (!place) throw new Error("Type a city and country, e.g. 'Leeds, United Kingdom'.");

    const geo = await geocode(place);
    const tags = (CATALOGUE[niche] || {}).tags || [];
    if (!tags.length) throw new Error("Unknown niche '" + niche + "'.");
    const [south, west, north, east] = geo.bbox;
    const box = "(" + south + "," + west + "," + north + "," + east + ")";
    const parts = [];
    for (const [k, v] of tags)
      for (const kind of ["node", "way"])
        parts.push('  ' + kind + '["' + k + '"="' + v + '"]["name"]' + box + ";");
    const query = "[out:json][timeout:90];\\n(\\n" + parts.join("\\n") + "\\n);\\nout center tags meta " + (limit * 4) + ";";
    const result = await overpass(query);

    const thin = THIN.has(geo.country_code);
    const minActivity = strict ? (thin ? 1 : 2) : 0;
    const placeLabel = geo.display_name.split(",")[0];

    let leads = [];
    for (const el of (result.elements || [])) {
      const t = el.tags || {};
      const name = (t.name || "").trim();
      if (!name || looksClosed(t)) continue;
      const edited = (el.timestamp || "").slice(0, 10);
      const act = activitySignals(t, edited);
      if (minActivity && act < minActivity) continue;
      const website = first(t, ["website", "contact:website", "url", "contact:url"]);
      const phone = first(t, ["phone", "contact:phone", "contact:mobile", "mobile"]);
      const ch = phoneChannels(phone, geo.country_code);
      const socials = {};
      for (const kind in SOCIAL_KEYS) { const v = first(t, SOCIAL_KEYS[kind]); if (v) socials[kind] = socialUrl(kind, v); }
      const lat = el.lat != null ? el.lat : (el.center || {}).lat;
      const lon = el.lon != null ? el.lon : (el.center || {}).lon;
      const addr = address(t);
      leads.push({
        id: (el.type || "n") + el.id,
        name: name, niche: niche, city: placeLabel, country: geo.country,
        address: addr, phone: phone,
        phone_e164: ch.e164 || "", whatsapp: ch.whatsapp || "",
        email: first(t, ["email", "contact:email"]),
        owner: first(t, ["operator", "owner", "contact:person", "name:etymology"]),
        website: website, socials: socials, links_ok: {},
        opening_hours: t.opening_hours || "",
        verified_date: t.check_date || t["survey:date"] || edited,
        lat: lat, lon: lon,
        osm_url: "https://www.openstreetmap.org/" + (el.type || "node") + "/" + el.id,
        activity: act, segment: (CATALOGUE[niche] || {}).seg || "",
        stage: "New", starred: 0, notes: "",
        maps_verify: mapsLinks(name, lat, lon, addr, placeLabel).maps_verify
      });
    }

    // de-duplicate node + way versions of the same shop
    const seen = new Set();
    leads = leads.filter(l => {
      const key = (l.name.toLowerCase() + "|" + (l.address || "").toLowerCase());
      if (seen.has(key)) return false;
      seen.add(key); return true;
    });

    const noSite = leads.filter(l => !l.website);
    const withSite = leads.filter(l => l.website);
    for (const l of noSite) { l.qualified = true; l.reason = "No website at all — only findable if you already know they exist"; }
    for (const l of withSite) {
      l.qualified = false;
      l.reason = "Has a website (health checks need the desktop app)";
    }

    let chosen, note = "";
    if (mode === "bad_website") {
      chosen = [];
      note = "Checking whether existing websites are dead needs the desktop app (browsers can't read other sites). Switch to 'No website at all' or 'Both' here.";
    } else if (mode === "all") {
      chosen = noSite.concat(withSite);
      note = "Website health-checks are off in this browser version — the desktop app flags dead sites automatically.";
    } else {
      chosen = noSite;
    }

    for (const l of chosen) { l.score = score(l); l.reachability = reachability(l); }
    chosen.sort((a, b) => b.score - a.score);
    chosen = chosen.slice(0, limit);

    dbInsert(chosen);

    return {
      place: geo.display_name, country: geo.country,
      scanned: (result.elements || []).length,
      found: chosen.length, new_leads: dbInsertCount, duplicates: chosen.length - dbInsertCount,
      filter_niche: niche,
      filter_city: chosen.length ? chosen[0].city : placeLabel,
      filter_country: chosen.length ? chosen[0].country : geo.country,
      whatsapp_count: chosen.filter(l => l.whatsapp).length,
      note: note, leads: chosen
    };
  }

  // ── saved-lead database (localStorage) ───────────────────────────────────
  const DB_KEY = "rlf_live_leads_v1";
  let dbInsertCount = 0;
  function dbLoad() { try { return JSON.parse(localStorage.getItem(DB_KEY) || "[]"); } catch (e) { return []; } }
  function dbSave(rows) { try { localStorage.setItem(DB_KEY, JSON.stringify(rows.slice(0, 800))); } catch (e) {} }
  function dbInsert(leads) {
    dbInsertCount = 0;
    const rows = dbLoad();
    const have = new Set(rows.map(r => r.id));
    for (const l of leads) if (!have.has(l.id)) { rows.push(l); have.add(l.id); dbInsertCount++; }
    dbSave(rows);
    return dbInsertCount;
  }
  function facets(rows) {
    const uniq = k => Array.from(new Set(rows.map(l => l[k]).filter(Boolean))).sort();
    return { niches: uniq("niche"), countries: uniq("country"), cities: uniq("city") };
  }
  function leadList(params) {
    let rows = dbLoad();
    const eq = (k, v) => { if (v) rows = rows.filter(l => l[k] === v); };
    eq("niche", params.get("niche")); eq("country", params.get("country"));
    eq("city", params.get("city")); eq("stage", params.get("stage"));
    if (params.get("starred")) rows = rows.filter(l => l.starred);
    const q = params.get("q");
    if (q) { const ql = q.toLowerCase(); rows = rows.filter(l => (l.name + " " + l.city).toLowerCase().includes(ql)); }
    rows.sort((a, b) => (b.starred - a.starred) || (b.score - a.score) || a.name.localeCompare(b.name));
    const stages = {};
    rows.forEach(l => { const s = l.stage || "New"; stages[s] = (stages[s] || 0) + 1; });
    return { leads: rows, stages: stages, starred_total: rows.filter(l => l.starred).length, total_all: dbLoad().length, facets: facets(dbLoad()) };
  }

  // ── message + brief templates (AI rewrites need the desktop app) ─────────
  function buildMessage(l, kind) {
    const price = PRICE[l.country] || "$250";
    const name = l.owner ? "Hi " + l.owner.split(" ")[0] : "Hi";
    if (kind === "email") {
      return name + ",\\n\\nI came across " + l.name + " on OpenStreetMap" +
        (l.city ? " in " + l.city : "") + " and noticed you don't seem to have a website yet. " +
        "A simple site would help people find you on Google and trust you instantly.\\n\\n" +
        "I build clean, fast websites for local businesses for around " + price + " — live in about a week.\\n\\n" +
        "Want me to put a quick demo together for " + l.name + "?\\n\\n— Sent from the Ripple Lead Finder live demo";
    }
    return name + "! Found " + l.name + (l.city ? " in " + l.city : "") +
      " — love what you're doing. Noticed there's no website showing up for you on Google though. " +
      "I build simple sites for local " + (l.niche || "businesses").toLowerCase() + " (~" + price + ", live in about a week). " +
      "Want me to mock one up for " + l.name + " so you can see it first? No pressure either way \\u{1F44D}";
  }

  function buildBrief(l) {
    return "BUSINESS BRIEF — " + l.name + "\\n" +
      "Industry: " + l.niche + "\\nLocation: " + [l.address, l.city, l.country].filter(Boolean).join(", ") + "\\n" +
      "Phone: " + (l.phone || "—") + "\\nEmail: " + (l.email || "—") + "\\n" +
      "Current website: " + (l.website || "NONE — they need a first site") + "\\n" +
      "Opening hours: " + (l.opening_hours || "—") + "\\n" +
      "Social: " + (Object.keys(l.socials).map(k => k + ": " + l.socials[k]).join(" | ") || "—") + "\\n\\n" +
      "Build them a simple one-page site: hero with name + photo, services, opening hours, " +
      "click-to-call phone button, Google Maps embed, and a contact form. Mobile-first — most " +
      "local customers browse on a phone.";
  }

  // ── town list per country (live Overpass, cached 24h) ────────────────────
  async function listCities(country) {
    const cacheKey = "rlf_live_cities_" + country;
    try {
      const hit = JSON.parse(localStorage.getItem(cacheKey) || "null");
      if (hit && hit.at > Date.now() - 864e5) return hit.cities;
    } catch (e) {}
    const iso = COUNTRY_ISO[country];
    if (!iso) throw new Error("No ISO code on file for '" + country + "'.");
    const q = '[out:json][timeout:60];area["ISO3166-1"="' + iso + '"]["admin_level"="2"]->.c;(node["place"="city"](area.c);node["place"="town"](area.c););out tags 1600;';
    const result = await overpass(q);
    const seen = new Set(), pops = [];
    for (const el of (result.elements || [])) {
      const t = el.tags || {};
      const name = (t["name:en"] || t.name || "").trim();
      if (!name || seen.has(name.toLowerCase())) continue;
      seen.add(name.toLowerCase());
      pops.push([parseInt((t.population || "0").replace(/\\D/g, "")) || 0, name]);
    }
    pops.sort((a, b) => b[0] - a[0] || a[1].localeCompare(b[1]));
    const cities = pops.slice(0, 400).map(x => x[1]);
    try { localStorage.setItem(cacheKey, JSON.stringify({ at: Date.now(), cities: cities })); } catch (e) {}
    return cities;
  }

  // ── fetch override ───────────────────────────────────────────────────────
  window.fetch = async function (input, init) {
    const url = typeof input === "string" ? input : (input && input.url) || "";
    const method = ((init && init.method) || (input && input.method) || "GET").toUpperCase();
    let body = {};
    try { body = init && init.body ? JSON.parse(init.body) : {}; } catch (e) {}
    const u = new URL(url, location.origin);
    const p = u.pathname;

    if (!p.startsWith("/api/")) return realFetch(input, init);

    try {
      if (p === "/api/niches") {
        const segs = {};
        Object.keys(CATALOGUE).sort().forEach(n => {
          const s = CATALOGUE[n].seg || "Other";
          (segs[s] = segs[s] || []).push(n);
        });
        return J({ has_openai: false, lang: "en", niches: Object.keys(CATALOGUE).sort(), segments: segs });
      }
      if (p === "/api/cities") return J({ cities: await listCities(u.searchParams.get("country")), source: "live" });
      if (p === "/api/health") return J({ ok: true });
      if (p === "/api/settings") return method === "POST" ? J({ ok: true }) : J({});
      if (p === "/api/search") return J(await runSearch(body));
      if (p === "/api/leads") return J(leadList(u.searchParams));
      if (p === "/api/brief") {
        const l = dbLoad().find(x => x.id === String(body.id));
        return J({ brief: l ? buildBrief(l) : "Demo page — run a live search first.", source: "template" });
      }
      if (p === "/api/message") {
        const l = dbLoad().find(x => x.id === String(body.id));
        return J({ message: l ? buildMessage(l, body.kind || "fb") : "Demo page — run a live search first.", source: "template" });
      }
      if (p === "/api/manual-link") return J({ error: "Manual link building needs the desktop app." });
      if (p === "/api/insta") return J({ error: "Instagram verification needs the desktop app." }, 400);

      const m = p.match(/^\\/api\\/lead\\/(.+)$/);
      if (m) {
        const id = decodeURIComponent(m[1]);
        const rows = dbLoad();
        const lead = rows.find(l => l.id === id);
        if (!lead) return J({ error: "Lead not found" }, 404);
        if (method === "DELETE") { dbSave(rows.filter(l => l.id !== id)); return J({ ok: true }); }
        ["stage", "notes", "phone", "email", "starred"].forEach(k => { if (body[k] !== undefined) lead[k] = body[k]; });
        dbSave(rows);
        return J({ ok: true });
      }

      if (p === "/api/export.csv") {
        const head = "name,niche,city,country,phone,email,website,score,stage";
        const esc = v => '"' + String(v == null ? "" : v).replace(/"/g, '""') + '"';
        const lines = dbLoad().map(l => [l.name, l.niche, l.city, l.country, l.phone, l.email, l.website, l.score, l.stage].map(esc).join(","));
        return new Response([head].concat(lines).join("\\n"), { headers: { "Content-Type": "text/csv" } });
      }

      return J({});
    } catch (err) {
      return J({ error: String(err.message || err) }, 400);
    }
  };
})();
</script>
"""


def build() -> None:
    html = __import__("pathlib").Path(ROOT / "dashboard.html").read_text(encoding="utf-8")

    for marker in ("LIVE SHIM", "Live search</b>"):
        if marker in html:
            sys.exit("dashboard.html already contains live markers — nothing to do")

    html = html.replace("<body>", "<body>" + BANNER, 1)
    idx = html.rindex("<script>")
    shim = SHIM.replace("__CATALOGUE__", json.dumps(CATALOGUE, ensure_ascii=False))
    html = html[:idx] + shim + "\n" + html[idx:]

    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({len(html):,} bytes)")


if __name__ == "__main__":
    build()
