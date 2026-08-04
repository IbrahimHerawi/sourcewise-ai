const DATE_FORMATTER = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

const RELATIVE_DATE_FORMATTER = new Intl.RelativeTimeFormat(undefined, {
  numeric: "auto",
});

export function formatDateTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Date unavailable" : DATE_FORMATTER.format(date);
}

export function formatRelativeDate(value: string): string {
  const date = new Date(value);
  const differenceMs = date.getTime() - Date.now();
  if (Number.isNaN(differenceMs)) return "Date unavailable";

  const minutes = Math.round(differenceMs / 60_000);
  if (Math.abs(minutes) < 60) return RELATIVE_DATE_FORMATTER.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return RELATIVE_DATE_FORMATTER.format(hours, "hour");
  const days = Math.round(hours / 24);
  if (Math.abs(days) < 7) return RELATIVE_DATE_FORMATTER.format(days, "day");
  return formatDateTime(value);
}

export function formatFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "Size unavailable";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = units[0];
  for (let index = 1; index < units.length && value >= 1024; index += 1) {
    value /= 1024;
    unit = units[index];
  }
  return `${new Intl.NumberFormat(undefined, { maximumFractionDigits: value < 10 ? 1 : 0 }).format(value)} ${unit}`;
}
