const WEEK = ["일", "월", "화", "수", "목", "금", "토"];

export function weekdayKo(iso: string) {
  const [y, m, d] = iso.split("-").map(Number);
  return WEEK[new Date(Date.UTC(y, m - 1, d)).getUTCDay()];
}

export function formatDotDate(iso: string) {
  return iso.replaceAll("-", ".");
}

export function formatDotWeek(iso: string) {
  return `${formatDotDate(iso)} ${weekdayKo(iso)}`;
}

export function rfc822(iso: string, hour = 7, minute = 20) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d, hour - 9, minute, 0)).toUTCString();
}
