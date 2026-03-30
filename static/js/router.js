export function parseRoute(hash) {
  const cleaned = String(hash || "#overview").replace(/^#/, "");
  const [view = "overview", item = ""] = cleaned.split("/");
  return {
    view: view || "overview",
    item: item ? decodeURIComponent(item) : null,
  };
}

export function navigate(view, item = "") {
  const suffix = item ? `/${encodeURIComponent(item)}` : "";
  window.location.hash = `#${view}${suffix}`;
}

