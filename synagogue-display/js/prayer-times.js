/*
 * Resolves a prayer's actual clock time for a given day, combining:
 *  - fixed times ("07:15")
 *  - times relative to a halachic anchor ("15 minutes before sunset")
 * using the zmanim fetched from Hebcal for that day.
 */

const PrayerTimes = (() => {
  const ANCHORS = {
    alot: { label: 'עלות השחר', zman: 'alotHaShachar' },
    netz: { label: 'הנץ החמה', zman: 'sunrise' },
    sofZmanShma: { label: 'סוף זמן ק"ש', zman: 'sofZmanShma' },
    sofZmanTfilla: { label: 'סוף זמן תפילה', zman: 'sofZmanTfilla' },
    chatzot: { label: 'חצות היום', zman: 'chatzot' },
    minchaGedola: { label: 'מנחה גדולה', zman: 'minchaGedola' },
    minchaKetana: { label: 'מנחה קטנה', zman: 'minchaKetana' },
    plag: { label: 'פלג המנחה', zman: 'plagHaMincha' },
    shkia: { label: 'שקיעה', zman: 'sunset' },
    tzeit: { label: 'צאת הכוכבים', zman: null }, // resolved dynamically via settings.tzeitMethod
  };

  function anchorOptions() {
    return Object.entries(ANCHORS).map(([key, v]) => ({ key, label: v.label }));
  }

  function anchorDate(anchorKey, zmanim, settings) {
    if (anchorKey === 'tzeit') return Hebcal.resolveTzeit(zmanim, settings.tzeitMethod);
    const def = ANCHORS[anchorKey];
    if (!def) return null;
    return Hebcal.zmanAsDate(zmanim, def.zman);
  }

  function resolve(prayer, zmanim, settings, forDate) {
    if (prayer.timeType === 'fixed') {
      const hm = parseHM(prayer.fixedTime);
      if (!hm) return null;
      const d = new Date(forDate);
      d.setHours(hm.h, hm.m, 0, 0);
      return d;
    }
    const base = anchorDate(prayer.anchor, zmanim, settings);
    if (!base) return null;
    return addMinutes(base, Number(prayer.offset) || 0);
  }

  function appliesToday(prayer, weekdayKey) {
    if (!prayer.days || prayer.days === 'all' || (Array.isArray(prayer.days) && prayer.days.length === 0)) {
      return true;
    }
    if (Array.isArray(prayer.days)) return prayer.days.includes(weekdayKey);
    return true;
  }

  return { ANCHORS, anchorOptions, anchorDate, resolve, appliesToday };
})();
