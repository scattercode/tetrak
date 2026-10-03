// Cloudflare Pages Function — first-party proxy for the Plausible event beacon.
//
// Purpose: receive Plausible's event POST at tetrak.dev/api/event (a first-party
// path that tracker blocklists do not match on the plausible.io domain) and
// forward it to Plausible's ingest endpoint.
//
// Critical: Plausible derives visitor geolocation and the daily unique-visitor
// hash from the client IP and User-Agent. Behind this proxy every request would
// otherwise arrive from Cloudflare's egress IP, so the real client IP must be
// forwarded as X-Forwarded-For (taken from CF-Connecting-IP) and the original
// User-Agent preserved. Without this, all visitors collapse to one location and
// unique counts are wrong.
//
// Companion function: functions/js/script.js.js proxies the tracking script,
// and carries the note on why this directory sits at the repository root.

const UPSTREAM_EVENT = "https://plausible.io/api/event";

export async function onRequestPost({ request }) {
  const headers = new Headers();
  headers.set("Content-Type", "application/json");
  headers.set("User-Agent", request.headers.get("User-Agent") || "");
  // Forward the real visitor IP so Plausible geolocates and counts correctly.
  const clientIp = request.headers.get("CF-Connecting-IP");
  if (clientIp) {
    headers.set("X-Forwarded-For", clientIp);
  }

  return fetch(UPSTREAM_EVENT, {
    method: "POST",
    headers,
    body: await request.text()
  });
}
