/*
 * Thin client for the public Hebcal REST APIs (no API key required):
 *  - https://www.hebcal.com/hebcal  -> parasha, holidays, candle lighting, havdalah, omer
 *  - https://www.hebcal.com/zmanim  -> halachic times for a given day/location
 *  - https://www.hebcal.com/converter -> Gregorian <-> Hebrew date conversion
 *
 * Results are cached in localStorage per day+location so the display keeps
 * working if the network drops for a while (per spec: "keep working today
 * even if the internet goes down briefly").
 */

const Hebcal = (() => {
  const CACHE_PREFIX = 'synagogue_hebcal_cache_';
  const CACHE_TTL_MS = 6 * 60 * 60 * 1000; // refresh at most every 6h when online

  function cacheKey(settings, dateISO) {
    return `${CACHE_PREFIX}${dateISO}_${settings.latitude}_${settings.longitude}`;
  }

  function readCache(key) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }

  function writeCache(key, data) {
    try {
      localStorage.setItem(key, JSON.stringify({ data, fetchedAt: Date.now() }));
    } catch (e) {
      console.warn('Hebcal: cache write failed (storage full?)', e);
    }
  }

  async function fetchJSON(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Hebcal request failed: ${res.status}`);
    return res.json();
  }

  async function getDayInfo(settings, dateISO) {
    const key = cacheKey(settings, dateISO) + '_day';
    const cached = readCache(key);
    if (cached && Date.now() - cached.fetchedAt < CACHE_TTL_MS) return cached.data;

    try {
      const params = new URLSearchParams({
        v: '1',
        cfg: 'json',
        maj: 'on',
        min: 'on',
        mod: 'on',
        nx: 'on',
        mf: 'on',
        ss: 'on',
        s: 'on',
        c: 'on',
        o: 'on', // omer
        F: 'on', // parasha
        latitude: String(settings.latitude),
        longitude: String(settings.longitude),
        tzid: settings.tzid,
        b: String(settings.candleLightingMinutes ?? 20),
        M: 'on', // use havdalah based on tzeit, we still read our own zmanim separately
        start: dateISO,
        end: dateISO,
      });
      const json = await fetchJSON(`https://www.hebcal.com/hebcal?${params.toString()}`);
      const parsed = parseDayItems(json.items || []);
      writeCache(key, parsed);
      return parsed;
    } catch (e) {
      console.warn('Hebcal day fetch failed, using cache if available', e);
      if (cached) return cached.data;
      return { parasha: null, holidays: [], candleLighting: null, havdalah: null, omer: null };
    }
  }

  function parseDayItems(items) {
    const result = { parasha: null, holidays: [], candleLighting: null, havdalah: null, omer: null };
    for (const item of items) {
      switch (item.category) {
        case 'parashat':
          result.parasha = item.hebrew || item.title;
          break;
        case 'candles':
          result.candleLighting = item.date;
          break;
        case 'havdalah':
          result.havdalah = item.date;
          break;
        case 'omer':
          result.omer = item.hebrew || item.title;
          break;
        case 'holiday':
        case 'roshchodesh':
        case 'mevarchim':
        case 'fast':
          result.holidays.push({ title: item.hebrew || item.title, category: item.category });
          break;
      }
    }
    return result;
  }

  async function getHebrewDate(dateISO) {
    const key = `${CACHE_PREFIX}${dateISO}_conv`;
    const cached = readCache(key);
    if (cached && Date.now() - cached.fetchedAt < CACHE_TTL_MS) return cached.data;
    try {
      const params = new URLSearchParams({ cfg: 'json', date: dateISO, g2h: '1' });
      const json = await fetchJSON(`https://www.hebcal.com/converter?${params.toString()}`);
      const data = { hebrew: json.hebrew, hy: json.hy, hm: json.hm, hd: json.hd };
      writeCache(key, data);
      return data;
    } catch (e) {
      console.warn('Hebcal date conversion failed, using cache if available', e);
      return cached ? cached.data : null;
    }
  }

  // Zmanim field names as returned by hebcal.com/zmanim (cfg=json), with
  // fallbacks since not every field is present for every location/date.
  const ZMAN_LABELS = {
    alotHaShachar: 'עלות השחר',
    misheyakir: 'משיכיר',
    sunrise: 'הנץ החמה',
    sofZmanShma: 'סוף זמן ק"ש (מג"א/גר"א)',
    sofZmanTfilla: 'סוף זמן תפילה',
    chatzot: 'חצות היום',
    minchaGedola: 'מנחה גדולה',
    minchaKetana: 'מנחה קטנה',
    plagHaMincha: 'פלג המנחה',
    sunset: 'שקיעה',
    tzeit7083deg: 'צאת הכוכבים',
    tzeit85deg: 'צאת הכוכבים',
    tzeit42min: 'צאת הכוכבים',
    tzeit72min: 'רבנו תם',
    chatzotNight: 'חצות הלילה',
  };

  async function getZmanim(settings, dateISO) {
    const key = cacheKey(settings, dateISO) + '_zman';
    const cached = readCache(key);
    if (cached && Date.now() - cached.fetchedAt < CACHE_TTL_MS) return cached.data;

    try {
      const params = new URLSearchParams({
        cfg: 'json',
        latitude: String(settings.latitude),
        longitude: String(settings.longitude),
        tzid: settings.tzid,
        date: dateISO,
      });
      const json = await fetchJSON(`https://www.hebcal.com/zmanim?${params.toString()}`);
      const times = json.times || {};
      const parsed = {};
      for (const [key2, val] of Object.entries(times)) {
        const d = new Date(val);
        if (!isNaN(d)) parsed[key2] = d.toISOString();
      }
      writeCache(key, parsed);
      return parsed;
    } catch (e) {
      console.warn('Hebcal zmanim fetch failed, using cache if available', e);
      return cached ? cached.data : {};
    }
  }

  function zmanAsDate(zmanim, key) {
    if (!zmanim || !zmanim[key]) return null;
    const d = new Date(zmanim[key]);
    return isNaN(d) ? null : d;
  }

  function resolveTzeit(zmanim, method) {
    const order = [method, 'tzeit7083deg', 'tzeit85deg', 'tzeit42min'];
    for (const key of order) {
      const d = zmanAsDate(zmanim, key);
      if (d) return d;
    }
    return null;
  }

  return { getDayInfo, getHebrewDate, getZmanim, zmanAsDate, resolveTzeit, ZMAN_LABELS };
})();
