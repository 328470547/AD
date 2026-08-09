import { Store } from './store.js';

(() => {
  let editingPrayerId = null;
  let editingLessonId = null;
  let editingAnnouncementId = null;

  // ---------------- Auth ----------------
  function showApp() {
    document.getElementById('loginWrap').style.display = 'none';
    document.getElementById('app').style.display = '';
    document.getElementById('appSynName').textContent = Store.getSettings().name;
    renderAll();
  }

  function showLogin() {
    document.getElementById('loginWrap').style.display = '';
    document.getElementById('app').style.display = 'none';
  }

  const AUTH_ERROR_MESSAGES = {
    'auth/invalid-credential': 'אימייל או סיסמה שגויים',
    'auth/wrong-password': 'סיסמה שגויה',
    'auth/user-not-found': 'לא נמצא משתמש עם אימייל זה',
    'auth/invalid-email': 'כתובת אימייל לא תקינה',
    'auth/too-many-requests': 'יותר מדי ניסיונות - נסה שוב בעוד כמה דקות',
    'auth/network-request-failed': 'בעיית תקשורת - בדוק את החיבור לאינטרנט',
  };

  async function handleLogin() {
    const errorEl = document.getElementById('loginError');
    errorEl.textContent = '';
    const email = document.getElementById('loginUser').value.trim();
    const pass = document.getElementById('loginPass').value;
    if (!email || !pass) {
      errorEl.textContent = 'נא להזין אימייל וסיסמה';
      return;
    }
    try {
      await Store.signIn(email, pass);
    } catch (e) {
      errorEl.textContent = AUTH_ERROR_MESSAGES[e.code] || 'שגיאה בהתחברות, נסה שוב';
    }
  }

  document.getElementById('loginBtn').addEventListener('click', handleLogin);
  document.getElementById('loginPass').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleLogin();
  });
  document.getElementById('logoutBtn').addEventListener('click', () => {
    Store.signOutUser();
  });

  Store.onAuthChange((user) => {
    if (user) showApp();
    else showLogin();
  });

  // ---------------- Tabs ----------------
  document.querySelectorAll('.tab-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach((p) => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    });
  });

  // ---------------- Toast ----------------
  function toast(msg) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.classList.add('show');
    setTimeout(() => el.classList.remove('show'), 1800);
  }

  // ---------------- Prayers ----------------
  function initPrayerForm() {
    const anchorSel = document.getElementById('pAnchor');
    anchorSel.innerHTML = PrayerTimes.anchorOptions()
      .map((a) => `<option value="${a.key}">${escapeHtml(a.label)}</option>`)
      .join('');

    const daysWrap = document.getElementById('pDays');
    daysWrap.innerHTML = WEEKDAY_KEYS.map(
      (key, i) => `<label><input type="checkbox" value="${key}" style="width:auto"> יום ${HEBREW_WEEKDAYS[i]}</label>`
    ).join('');

    document.getElementById('pTimeType').addEventListener('change', (e) => {
      const rel = e.target.value === 'relative';
      document.getElementById('pFixedRow').style.display = rel ? 'none' : '';
      document.getElementById('pRelativeRow').style.display = rel ? '' : 'none';
    });
  }

  function resetPrayerForm() {
    editingPrayerId = null;
    document.getElementById('pAddBtn').textContent = 'הוספה';
    document.getElementById('pName').value = '';
    document.getElementById('pFixedTime').value = '';
    document.getElementById('pOffsetMin').value = 0;
    document.getElementById('pNote').value = '';
    document.querySelectorAll('#pDays input').forEach((c) => (c.checked = false));
  }

  function collectPrayerForm() {
    const name = document.getElementById('pName').value.trim();
    if (!name) {
      toast('נא להזין שם תפילה');
      return null;
    }
    const timeType = document.getElementById('pTimeType').value;
    const days = [...document.querySelectorAll('#pDays input:checked')].map((c) => c.value);
    const item = { name, timeType, days, note: document.getElementById('pNote').value.trim() };
    if (timeType === 'fixed') {
      const t = document.getElementById('pFixedTime').value;
      if (!t) {
        toast('נא לבחור שעה');
        return null;
      }
      item.fixedTime = t;
    } else {
      const beforeAfter = document.getElementById('pBeforeAfter').value;
      const mins = Math.abs(Number(document.getElementById('pOffsetMin').value) || 0);
      item.anchor = document.getElementById('pAnchor').value;
      item.offset = beforeAfter === 'before' ? -mins : mins;
    }
    return item;
  }

  document.getElementById('pAddBtn').addEventListener('click', async () => {
    const item = collectPrayerForm();
    if (!item) return;
    try {
      if (editingPrayerId) {
        await Store.updateItem('prayers', editingPrayerId, item);
        toast('התפילה עודכנה');
      } else {
        await Store.addItem('prayers', item);
        toast('התפילה נוספה');
      }
      resetPrayerForm();
    } catch (e) {
      toast('שגיאה בשמירה: ' + (e.message || e));
    }
  });

  function describePrayer(p) {
    const days = Array.isArray(p.days) && p.days.length
      ? p.days.map((d) => HEBREW_WEEKDAYS[WEEKDAY_KEYS.indexOf(d)]).join(', ')
      : 'כל יום';
    if (p.timeType === 'fixed') return `${p.fixedTime} · ${days}`;
    const anchorLabel = PrayerTimes.ANCHORS[p.anchor]?.label || p.anchor;
    const dir = p.offset < 0 ? 'לפני' : 'אחרי';
    return `${Math.abs(p.offset)} דק' ${dir} ${anchorLabel} · ${days}`;
  }

  function renderPrayersList() {
    const list = Store.getList('prayers');
    const el = document.getElementById('prayersList');
    el.innerHTML = '';
    for (const p of list) {
      const card = document.createElement('div');
      card.className = 'item-card card';
      card.innerHTML = `
        <div class="info">
          <div class="title">${escapeHtml(p.name)}</div>
          <div class="meta">${escapeHtml(describePrayer(p))}${p.note ? ' · ' + escapeHtml(p.note) : ''}</div>
        </div>
        <div class="actions">
          <button class="secondary" data-edit="${p.id}">עריכה</button>
          <button class="danger" data-del="${p.id}">מחיקה</button>
        </div>`;
      el.appendChild(card);
    }
    el.querySelectorAll('[data-del]').forEach((b) =>
      b.addEventListener('click', async () => {
        await Store.deleteItem('prayers', b.dataset.del);
        toast('נמחק');
      })
    );
    el.querySelectorAll('[data-edit]').forEach((b) =>
      b.addEventListener('click', () => {
        const p = list.find((x) => x.id === b.dataset.edit);
        editingPrayerId = p.id;
        document.getElementById('pAddBtn').textContent = 'עדכון';
        document.getElementById('pName').value = p.name;
        document.getElementById('pTimeType').value = p.timeType;
        document.getElementById('pTimeType').dispatchEvent(new Event('change'));
        document.getElementById('pFixedTime').value = p.fixedTime || '';
        document.getElementById('pAnchor').value = p.anchor || '';
        document.getElementById('pBeforeAfter').value = (p.offset || 0) < 0 ? 'before' : 'after';
        document.getElementById('pOffsetMin').value = Math.abs(p.offset || 0);
        document.getElementById('pNote').value = p.note || '';
        document.querySelectorAll('#pDays input').forEach((c) => (c.checked = (p.days || []).includes(c.value)));
        window.scrollTo({ top: 0, behavior: 'smooth' });
      })
    );
  }

  // ---------------- Lessons ----------------
  document.getElementById('lRecurring').addEventListener('change', (e) => {
    const recurring = e.target.value === '1';
    document.getElementById('lDayWrap').style.display = recurring ? '' : 'none';
    document.getElementById('lDateWrap').style.display = recurring ? 'none' : '';
  });

  function resetLessonForm() {
    editingLessonId = null;
    document.getElementById('lAddBtn').textContent = 'הוספה';
    document.getElementById('lTitle').value = '';
    document.getElementById('lRabbi').value = '';
    document.getElementById('lTime').value = '';
    document.getElementById('lDate').value = '';
  }

  document.getElementById('lAddBtn').addEventListener('click', async () => {
    const title = document.getElementById('lTitle').value.trim();
    if (!title) {
      toast('נא להזין שם שיעור');
      return;
    }
    const recurring = document.getElementById('lRecurring').value === '1';
    const item = {
      title,
      rabbi: document.getElementById('lRabbi').value.trim(),
      recurring,
      time: document.getElementById('lTime').value,
      dayOfWeek: recurring ? document.getElementById('lDayOfWeek').value : null,
      date: recurring ? null : document.getElementById('lDate').value,
    };
    try {
      if (editingLessonId) {
        await Store.updateItem('lessons', editingLessonId, item);
        toast('השיעור עודכן');
      } else {
        await Store.addItem('lessons', item);
        toast('השיעור נוסף');
      }
      resetLessonForm();
    } catch (e) {
      toast('שגיאה בשמירה: ' + (e.message || e));
    }
  });

  function renderLessonsList() {
    const list = Store.getList('lessons');
    const el = document.getElementById('lessonsList');
    el.innerHTML = '';
    for (const l of list) {
      const when = l.recurring
        ? `כל יום ${HEBREW_WEEKDAYS[WEEKDAY_KEYS.indexOf(l.dayOfWeek)]}`
        : l.date || 'ללא תאריך';
      const card = document.createElement('div');
      card.className = 'item-card card';
      card.innerHTML = `
        <div class="info">
          <div class="title">${escapeHtml(l.title)}${l.rabbi ? ' · ' + escapeHtml(l.rabbi) : ''}</div>
          <div class="meta">${escapeHtml(when)} ${escapeHtml(l.time || '')}</div>
        </div>
        <div class="actions">
          <button class="secondary" data-edit="${l.id}">עריכה</button>
          <button class="danger" data-del="${l.id}">מחיקה</button>
        </div>`;
      el.appendChild(card);
    }
    el.querySelectorAll('[data-del]').forEach((b) =>
      b.addEventListener('click', async () => {
        await Store.deleteItem('lessons', b.dataset.del);
        toast('נמחק');
      })
    );
    el.querySelectorAll('[data-edit]').forEach((b) =>
      b.addEventListener('click', () => {
        const l = list.find((x) => x.id === b.dataset.edit);
        editingLessonId = l.id;
        document.getElementById('lAddBtn').textContent = 'עדכון';
        document.getElementById('lTitle').value = l.title;
        document.getElementById('lRabbi').value = l.rabbi || '';
        document.getElementById('lRecurring').value = l.recurring ? '1' : '0';
        document.getElementById('lRecurring').dispatchEvent(new Event('change'));
        document.getElementById('lDayOfWeek').value = l.dayOfWeek || 'sun';
        document.getElementById('lDate').value = l.date || '';
        document.getElementById('lTime').value = l.time || '';
        window.scrollTo({ top: 0, behavior: 'smooth' });
      })
    );
  }

  // ---------------- Announcements ----------------
  document.getElementById('aAddBtn').addEventListener('click', async () => {
    const text = document.getElementById('aText').value.trim();
    if (!text) {
      toast('נא להזין תוכן הודעה');
      return;
    }
    const btn = document.getElementById('aAddBtn');
    btn.disabled = true;
    try {
      const hours = Number(document.getElementById('aExpireHours').value) || 0;
      const item = { text, expiresAt: hours > 0 ? Date.now() + hours * 3600000 : null };
      const file = document.getElementById('aImage').files[0];
      if (file) {
        item.imageUrl = await Store.uploadImage(file, 'announcements');
      }
      if (editingAnnouncementId) {
        await Store.updateItem('announcements', editingAnnouncementId, item);
        toast('ההודעה עודכנה');
      } else {
        await Store.addItem('announcements', item);
        toast('ההודעה נוספה');
      }
      editingAnnouncementId = null;
      document.getElementById('aAddBtn').textContent = 'הוספה';
      document.getElementById('aText').value = '';
      document.getElementById('aExpireHours').value = '';
      document.getElementById('aImage').value = '';
    } catch (e) {
      toast('שגיאה בשמירה: ' + (e.message || e));
    } finally {
      btn.disabled = false;
    }
  });

  function renderAnnouncementsList() {
    const list = Store.getList('announcements');
    const el = document.getElementById('announcementsList');
    el.innerHTML = '';
    for (const a of list) {
      const meta = a.expiresAt ? `נעלמת ב-${new Date(a.expiresAt).toLocaleString('he-IL')}` : 'ללא תפוגה';
      const card = document.createElement('div');
      card.className = 'item-card card';
      card.innerHTML = `
        <div class="info">
          <div class="title">${escapeHtml(a.text)}</div>
          <div class="meta">${escapeHtml(meta)}</div>
        </div>
        <div class="actions">
          <button class="danger" data-del="${a.id}">מחיקה</button>
        </div>`;
      el.appendChild(card);
    }
    el.querySelectorAll('[data-del]').forEach((b) =>
      b.addEventListener('click', async () => {
        await Store.deleteItem('announcements', b.dataset.del);
        toast('נמחק');
      })
    );
  }

  // ---------------- Settings ----------------
  function fillSettingsForm() {
    const s = Store.getSettings();
    document.getElementById('sName').value = s.name;
    document.getElementById('sCity').value = s.city;
    document.getElementById('sLat').value = s.latitude;
    document.getElementById('sLon').value = s.longitude;
    document.getElementById('sTzid').value = s.tzid;
    document.getElementById('sNusach').value = s.nusach;
    document.getElementById('sCandle').value = s.candleLightingMinutes;
    document.getElementById('sTzeit').value = s.tzeitMethod;
    document.getElementById('sRabbeinuTam').checked = !!s.showRabbeinuTam;
    document.getElementById('sFontScale').value = s.fontScale;
    document.getElementById('sColor').value = s.primaryColor;
  }

  document.getElementById('sSaveBtn').addEventListener('click', async () => {
    const btn = document.getElementById('sSaveBtn');
    btn.disabled = true;
    try {
      const patch = {
        name: document.getElementById('sName').value.trim() || 'בית הכנסת',
        city: document.getElementById('sCity').value.trim(),
        latitude: Number(document.getElementById('sLat').value),
        longitude: Number(document.getElementById('sLon').value),
        tzid: document.getElementById('sTzid').value.trim() || 'Asia/Jerusalem',
        nusach: document.getElementById('sNusach').value,
        candleLightingMinutes: Number(document.getElementById('sCandle').value) || 0,
        tzeitMethod: document.getElementById('sTzeit').value,
        showRabbeinuTam: document.getElementById('sRabbeinuTam').checked,
        fontScale: Number(document.getElementById('sFontScale').value) || 1,
        primaryColor: document.getElementById('sColor').value,
      };
      const file = document.getElementById('sLogo').files[0];
      if (file) {
        patch.logoUrl = await Store.uploadImage(file, 'logos');
      }
      await Store.saveSettings(patch);
      document.getElementById('appSynName').textContent = patch.name;
      toast('ההגדרות נשמרו');
    } catch (e) {
      toast('שגיאה בשמירה: ' + (e.message || e));
    } finally {
      btn.disabled = false;
    }
  });

  // ---------------- Backup (local download only - source of truth lives in Firestore) ----------------
  document.getElementById('exportBtn').addEventListener('click', () => {
    const data = {
      settings: Store.getSettings(),
      prayers: Store.getList('prayers'),
      lessons: Store.getList('lessons'),
      announcements: Store.getList('announcements'),
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `synagogue-backup-${dateToISODate(new Date())}.json`;
    a.click();
    URL.revokeObjectURL(url);
  });

  // ---------------- Init ----------------
  function renderAll() {
    fillSettingsForm();
    renderPrayersList();
    renderLessonsList();
    renderAnnouncementsList();
  }

  initPrayerForm();
  document.getElementById('pTimeType').dispatchEvent(new Event('change'));
  document.getElementById('lRecurring').dispatchEvent(new Event('change'));

  Store.onChange(() => {
    if (document.getElementById('app').style.display !== 'none') renderAll();
  });
})();
