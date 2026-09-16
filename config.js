window.APP_CONFIG = {
  API_BASE:
    location.hostname === "gutentag-cloud.github.io"
      ? "https://mtr-live-train-map-api.onrender.com"
      : ""
};

// GitHub Pages is static-only, so same-origin /api calls would return GitHub's HTML
// 404 page there. Route them to the Render backend declared in render.yaml while
// keeping same-origin behaviour when serve_live.py hosts the page locally.
// No upstream credential is embedded here or ever served to the browser.
window.API = (window.APP_CONFIG && window.APP_CONFIG.API_BASE) || "";
window.apiFetch = function (url, opts) {
  return fetch(window.API + url, Object.assign({ cache: "no-store" }, opts || {})).then(function (r) {
    if (!r.ok) {
      const hint =
        r.status === 404
          ? " — no live backend on this host (GitHub Pages is static; run serve_live.py locally or check the Render API service)"
          : r.status >= 502 && r.status <= 504
          ? " — backend cold-starting (Render free tier sleeps) or offline; retrying"
          : "";
      throw new Error("HTTP " + r.status + hint);
    }
    return r;
  });
};
