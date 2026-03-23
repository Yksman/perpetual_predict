import { format, formatDistanceToNow, parseISO } from 'date-fns';

export function formatPct(value: number, decimals = 2): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
}

export function formatPnl(value: number, decimals = 2): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}`;
}

export function formatPrice(value: number): string {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function formatDate(isoString: string): string {
  return format(parseISO(isoString), 'yyyy-MM-dd HH:mm');
}

export function formatShortDate(isoString: string): string {
  return format(parseISO(isoString), 'MM/dd HH:mm');
}

export function formatTimeAgo(isoString: string): string {
  return formatDistanceToNow(parseISO(isoString), { addSuffix: true });
}
