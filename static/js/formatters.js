export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function formatPrice(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return number.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function formatNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return number.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

export function formatPct(value, digits = 1) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return `${(number * 100).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`;
}

export function formatPnl(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return `${number > 0 ? "+" : ""}${number.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatDate(value) {
  if (!value) return "-";
  const date = new Date(String(value).includes("T") ? value : `${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
}

export function signalTone(direction) {
  if (direction === "long") return "green";
  if (direction === "short") return "red";
  return "slate";
}

export function actionTone(action) {
  if (action === "add") return "green";
  if (action === "reduce") return "amber";
  if (action === "close") return "red";
  if (action === "maintain") return "slate";
  return "slate";
}

export function reliabilityTone(label) {
  if (!label) return "slate";
  const lower = String(label).toLowerCase();
  if (lower.includes("high")) return "green";
  if (lower.includes("medium")) return "amber";
  return "slate";
}

export function buildSparklinePath(values, width = 360, height = 120) {
  if (!values.length) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  return values
    .map((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * width;
      const y = height - ((value - min) / range) * height;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

export function compactList(values, limit = 3) {
  if (!Array.isArray(values) || values.length === 0) return "-";
  const visible = values.slice(0, limit);
  const extra = values.length - visible.length;
  return extra > 0 ? `${visible.join(", ")} +${extra}` : visible.join(", ");
}

export function humanizeKey(value) {
  return String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

