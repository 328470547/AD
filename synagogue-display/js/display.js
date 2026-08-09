import { Store } from './store.js';

(() => {
  let settings = Store.getSettings();
  let today = { dayInfo: null, hebrewDate: null, zmanim: {}, resolvedPrayers: [] };
  let tomorrow = { zmanim: {}, resolvedPrayers: [] };
  let tickerQueue = [];
  let tickerIdx = 0;

  function applyTheme() {
    document.documentElement.style.setProperty('--primary', settings.primaryColor || '#2f6fed');
    document.documentElement.style.setProperty('--font-scale', settings.fontScale || 1);
    document.getElementById('synName').textContent = settings.name || 'בית הכנסת';
    document.getElementById('synCity').textContent = settings.city || '';
    const logo = document.getElementById('logoImg');
    if (settings.logoUrl) {
      logo.src = settings.logoUrl;
      logo.style.display = '';
    } else {
      logo.style.display = 'none';
    }
  }

  function weekdayKeyFor(date) {
    return WEEKDAY_KEYS[date.getDay()];
  }

  function resolvePrayersForDate(date, zmanim) {
    const wk = weekdayKeyFor(date);
    const prayers = Store.getList('prayers');
    return prayers
      .filter((p) => PrayerTimes.appliesToday(p, wk))
      .map((p) => ({ prayer: p, time: PrayerTimes.resolve(p, zmanim, settings, date) }))
      .filter((r) => r.time)
      .sort((a, b) => a.time - b.time);
  }

  async function loadDayData() {
    const now = new Date();
    const todayISO = dateToISODate(now);
    const tmr = new Date(now);
    tmr.setDate(tmr.getDate() + 1);
    const tmrISO = dateToISODate(tmr);

    const [dayInfo, hebrewDate, zmanim] = await Promise.all([
      Hebcal.getDayInfo(settings, todayISO),
      Hebcal.getHebrewDate(todayISO),
      Hebcal.getZmanim(settings, todayISO),
    ]);
    today = { dayInfo, hebrewDate, zmanim, resolvedPrayers: resolvePrayersForDate(now, zmanim) };

    const tmrZmanim = await Hebcal.getZmanim(settings, tmrISO);
    tomorrow = { zmanim: tmrZmanim, resolvedPrayers: resolvePrayersForDate(tmr, tmrZmanim) };

    renderDateStrip();
    renderZmanim();
    renderShabbat();
    renderPrayers();
    renderLessons();
  }

  function renderDateStrip() {
    const hd = today.hebrewDate;
    document.getElementById('hebrewDate').textContent = hd ? hd.hebrew : 'תאריך עברי לא זמין';
    document.getElementById('parasha').textContent = today.dayInfo?.parasha
      ? `פרשת ${today.dayInfo.parasha}`
      : '';
    document.getElementById('omerTag').textContent = today.dayInfo?.omer || '';
    const tagsEl = document.getElementById('holidayTags');
    tagsEl.innerHTML = '';
    for (const h of today.dayInfo?.holidays || []) {
      const span = document.createElement('span');
      span.className = 'holiday-tag';
      span.textContent = h.title;
      tagsEl.appendChild(span);
    }
  }

  function renderZmanim() {
    const rows = [
      ['alotHaShachar', 'עלות השחר'],
      ['sunrise', 'הנץ החמה'],
      ['sofZmanShma', 'סוף זמן ק"ש'],
      ['sofZmanTfilla', 'סוף זמן תפילה'],
      ['chatzot', 'חצות היום'],
      ['minchaGedola', 'מנחה גדולה'],
      ['minchaKetana', 'מנחה קטנה'],
      ['plagHaMincha', 'פלג המנחה'],
      ['sunset', 'שקיעה'],
    ];
    const list = document.getElementById('zmanList');
    list.innerHTML = '';
    for (const [key, label] of rows) {
      const d = Hebcal.zmanAsDate(today.zmanim, key);
      list.appendChild(makeRow('zman-row', label, formatHM(d)));
    }
    const tzeit = Hebcal.resolveTzeit(today.zmanim, settings.tzeitMethod);
    list.appendChild(makeRow('zman-row', 'צאת הכוכבים', formatHM(tzeit)));
    if (settings.showRabbeinuTam) {
      const rt = Hebcal.zmanAsDate(today.zmanim, 'tzeit72min');
      list.appendChild(makeRow('zman-row', 'רבנו תם', formatHM(rt)));
    }
  }

  function makeRow(cls, name, time) {
    const row = document.createElement('div');
    row.className = cls;
    row.innerHTML = `<span class="name">${escapeHtml(name)}</span><span class="time">${escapeHtml(time)}</span>`;
    return row;
  }

  function renderShabbat() {
    const block = document.getElementById('shabbatBlock');
    const candle = today.dayInfo?.candleLighting;
    const havdalah = today.dayInfo?.havdalah;
    if (!candle && !havdalah) {
      block.style.display = 'none';
      return;
    }
    block.style.display = '';
    document.getElementById('candleTime').textContent = candle ? formatHM(new Date(candle)) : '--:--';
    document.getElementById('havdalahTime').textContent = havdalah ? formatHM(new Date(havdalah)) : '--:--';
  }

  function renderPrayers() {
    const list = document.getElementById('prayerList');
    list.innerHTML = '';
    const now = new Date();
    if (today.resolvedPrayers.length === 0) {
      list.innerHTML = '<div class="prayer-row"><span class="name">אין תפילות מוגדרות</span></div>';
    }
    for (const { prayer, time } of today.resolvedPrayers) {
      const row = document.createElement('div');
      const isNext = getNextPrayer()?.prayer === prayer;
      row.className = 'prayer-row' + (isNext ? ' active' : '');
      row.innerHTML = `<span class="name">${escapeHtml(prayer.name)}${prayer.note ? ' · ' + escapeHtml(prayer.note) : ''}</span><span class="time">${formatHM(time)}</span>`;
      list.appendChild(row);
    }
  }

  function getNextPrayer() {
    const now = new Date();
    const upcoming = [...today.resolvedPrayers, ...tomorrow.resolvedPrayers].filter((r) => r.time > now);
    return upcoming.length ? upcoming[0] : null;
  }

  function renderNextPrayer() {
    const next = getNextPrayer();
    const nameEl = document.getElementById('nextPrayerName');
    const timeEl = document.getElementById('nextPrayerTime');
    const cdEl = document.getElementById('countdown');
    if (!next) {
      nameEl.textContent = '—';
      timeEl.textContent = '--:--';
      cdEl.textContent = '';
      return;
    }
    nameEl.textContent = next.prayer.name;
    timeEl.textContent = formatHM(next.time);
    const diff = Math.max(0, next.time - new Date());
    const h = Math.floor(diff / 3600000);
    const m = Math.floor((diff % 3600000) / 60000);
    const s = Math.floor((diff % 60000) / 1000);
    cdEl.textContent = `${pad2(h)}:${pad2(m)}:${pad2(s)}`;
  }

  function renderLessons() {
    const wk = weekdayKeyFor(new Date());
    const lessons = Store.getList('lessons')
      .filter((l) => (l.recurring ? l.dayOfWeek === wk : l.date === dateToISODate(new Date())))
      .sort((a, b) => (a.time || '').localeCompare(b.time || ''));
    const list = document.getElementById('lessonList');
    list.innerHTML = '';
    if (lessons.length === 0) {
      list.innerHTML = '<div class="lesson-row"><span class="name">אין שיעורים היום</span></div>';
      return;
    }
    for (const l of lessons) {
      const row = document.createElement('div');
      row.className = 'lesson-row';
      row.innerHTML = `<span class="name">${escapeHtml(l.title)}${l.rabbi ? ' · ' + escapeHtml(l.rabbi) : ''}</span><span class="time">${escapeHtml(l.time || '')}</span>`;
      list.appendChild(row);
    }
  }

  function refreshTickerQueue() {
    const anns = Store.getActiveAnnouncements().map((a) => ({ title: 'הודעה', text: a.text, imageUrl: a.imageUrl }));
    tickerQueue = anns;
    tickerIdx = 0;
    const wrap = document.getElementById('tickerWrap');
    wrap.style.display = tickerQueue.length ? '' : 'none';
    showTickerItem();
  }

  function showTickerItem() {
    const el = document.getElementById('tickerItem');
    if (!tickerQueue.length) return;
    const item = tickerQueue[tickerIdx % tickerQueue.length];
    const img = item.imageUrl ? `<img src="${escapeHtml(item.imageUrl)}" alt="">` : '';
    el.innerHTML = `${img}<span class="title">${escapeHtml(item.title)}</span>${escapeHtml(item.text)}`;
    tickerIdx++;
  }

  function tickClock() {
    const now = new Date();
    document.getElementById('clock').textContent = formatHMS(now);
    document.getElementById('gregDate').textContent = now.toLocaleDateString('he-IL', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
    renderNextPrayer();
  }

  function setupOnlineBadge() {
    const badge = document.getElementById('offlineBadge');
    const update = () => badge.classList.toggle('show', !navigator.onLine);
    window.addEventListener('online', update);
    window.addEventListener('offline', update);
    update();
  }

  let lastLoadedDate = dateToISODate(new Date());
  function watchMidnightRollover() {
    setInterval(() => {
      const nowISO = dateToISODate(new Date());
      if (nowISO !== lastLoadedDate) {
        lastLoadedDate = nowISO;
        loadDayData();
      }
    }, 30000);
  }

  async function init() {
    applyTheme();
    setupOnlineBadge();
    await loadDayData();
    refreshTickerQueue();
    tickClock();
    setInterval(tickClock, 1000);
    setInterval(refreshTickerQueue, 20000);
    setInterval(showTickerItem, 8000);
    watchMidnightRollover();

    Store.onChange(() => {
      settings = Store.getSettings();
      applyTheme();
      today.resolvedPrayers = resolvePrayersForDate(new Date(), today.zmanim);
      renderPrayers();
      renderLessons();
      refreshTickerQueue();
    });
  }

  init();
})();
