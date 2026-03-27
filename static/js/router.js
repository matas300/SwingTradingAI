export function parseRoute(hash) {
  const cleaned = String(hash || "#overview").replace(/^#/, "");
  const [view = "overview", ticker = ""] = cleaned.split("/");
  return {
    view: view || "overview",
    ticker: ticker ? decodeURIComponent(ticker).toUpperCase() : null,
  };
}

export function navigate(view, ticker = "") {
  const suffix = ticker ? `/${encodeURIComponent(ticker)}` : "";
  window.location.hash = `#${view}${suffix}`;
}
