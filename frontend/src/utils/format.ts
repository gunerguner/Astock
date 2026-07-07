export function formatAmount(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '-';
  }
  const units: [string, number][] = [
    ['万亿', 1e12],
    ['亿', 1e8],
    ['万', 1e4],
  ];
  const matched = units.find(([, base]) => Math.abs(value) >= base);
  if (matched) {
    const [label, base] = matched;
    return `${(value / base).toFixed(2)}${label}`;
  }
  return `${value.toFixed(0)}元`;
}

export function formatPoint(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '-';
  }
  return value.toFixed(2);
}

export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '--';
  }
  return value.toFixed(2);
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '--';
  }
  const prefix = value > 0 ? '+' : '';
  return `${prefix}${value.toFixed(2)}%`;
}

export function getPercentColor(
  value: number | null | undefined
): string | undefined {
  if (value === null || value === undefined) {
    return undefined;
  }
  if (value > 0) {
    return '#00b42a';
  }
  if (value < 0) {
    return '#f53f3f';
  }
  return undefined;
}

export function formatPeriod(start: string, end: string): string {
  return `${start} ~ ${end}`;
}
