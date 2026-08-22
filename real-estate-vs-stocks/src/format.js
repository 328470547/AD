export function fmtILS(n, opts = {}) {
  const { compact = false, showSign = false } = opts;
  const sign = n < 0 ? '-' : showSign ? '+' : '';
  const abs = Math.abs(n);
  if (compact) {
    if (abs >= 1_000_000) return `${sign}₪${(abs / 1_000_000).toFixed(2)}M`;
    if (abs >= 1_000) return `${sign}₪${(abs / 1_000).toFixed(0)}K`;
  }
  return `${sign}₪${Math.round(abs).toLocaleString('en-US')}`;
}

export function fmtPct(n, d = 1) {
  return `${n.toFixed(d)}%`;
}
