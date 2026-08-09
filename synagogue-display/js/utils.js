/* Small shared helpers used by both the display screen and the admin panel. */

const HEBREW_WEEKDAYS = ['ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת'];
const WEEKDAY_KEYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];

function uid() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}

function pad2(n) {
  return String(n).padStart(2, '0');
}

function dateToISODate(d) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

function formatHM(date) {
  if (!(date instanceof Date) || isNaN(date)) return '--:--';
  return `${pad2(date.getHours())}:${pad2(date.getMinutes())}`;
}

function formatHMS(date) {
  if (!(date instanceof Date) || isNaN(date)) return '--:--:--';
  return `${pad2(date.getHours())}:${pad2(date.getMinutes())}:${pad2(date.getSeconds())}`;
}

function parseHM(str) {
  const m = /^(\d{1,2}):(\d{2})$/.exec((str || '').trim());
  if (!m) return null;
  return { h: Number(m[1]), m: Number(m[2]) };
}

function addMinutes(date, minutes) {
  return new Date(date.getTime() + minutes * 60000);
}

function debounce(fn, wait) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), wait);
  };
}

async function sha256Hex(text) {
  const enc = new TextEncoder().encode(text);
  const buf = await crypto.subtle.digest('SHA-256', enc);
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, '0')).join('');
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str == null ? '' : String(str);
  return div.innerHTML;
}
