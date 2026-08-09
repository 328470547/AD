/*
 * Data layer for the synagogue system.
 *
 * MVP implementation: everything is kept in the browser's localStorage,
 * on a single JSON document that mirrors the Firestore shape the project
 * will eventually move to:
 *
 *   synagogues/{synagogueId} = { settings, prayers, lessons, announcements, halacha, auth }
 *
 * IMPORTANT LIMITATION: localStorage is per-browser. The admin panel (gabbai's
 * phone) and the display screen (the TV's browser) will NOT see each other's
 * changes unless they share the same browser profile. This is fine for
 * building/testing the first version on one device. To make the gabbai's
 * phone update the TV in real time, this module needs to be swapped for a
 * real backend (Firebase Firestore is the planned one) - see README.md.
 *
 * Every other file talks to the data only through the `Store` object below,
 * so swapping the implementation later means rewriting this file only.
 */

const Store = (() => {
  const STORAGE_KEY = 'synagogue_v1';
  const CHANNEL_NAME = 'synagogue_sync_v1';

  const DEFAULT_DATA = {
    settings: {
      name: 'בית הכנסת',
      city: 'ירושלים',
      latitude: 31.7683,
      longitude: 35.2137,
      tzid: 'Asia/Jerusalem',
      nusach: 'ashkenaz',
      candleLightingMinutes: 20,
      tzeitMethod: 'tzeit7083deg',
      showRabbeinuTam: false,
      fontScale: 1,
      primaryColor: '#2f6fed',
      logoUrl: '',
    },
    prayers: [],
    lessons: [],
    announcements: [],
    halacha: [],
    auth: null, // { salt, hash } - set on first admin login
  };

  let cache = null;
  let channel = null;
  try {
    channel = new BroadcastChannel(CHANNEL_NAME);
  } catch (e) {
    channel = null; // Safari private mode / very old browsers
  }
  const listeners = new Set();

  function load() {
    if (cache) return cache;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      cache = raw ? deepMerge(DEFAULT_DATA, JSON.parse(raw)) : structuredClone(DEFAULT_DATA);
    } catch (e) {
      console.error('Store: failed to read localStorage, starting fresh', e);
      cache = structuredClone(DEFAULT_DATA);
    }
    return cache;
  }

  function deepMerge(base, override) {
    const out = structuredClone(base);
    for (const key of Object.keys(out)) {
      if (override && override[key] !== undefined) {
        if (
          typeof out[key] === 'object' &&
          out[key] !== null &&
          !Array.isArray(out[key]) &&
          typeof override[key] === 'object'
        ) {
          out[key] = { ...out[key], ...override[key] };
        } else {
          out[key] = override[key];
        }
      }
    }
    return out;
  }

  function persist(notifySelf = true) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cache));
    if (channel) channel.postMessage({ type: 'change', at: Date.now() });
    if (notifySelf) notifyListeners();
  }

  function notifyListeners() {
    for (const cb of listeners) {
      try {
        cb(cache);
      } catch (e) {
        console.error('Store listener error', e);
      }
    }
  }

  // Cross-tab / cross-window updates (same browser only, see limitation above)
  if (channel) {
    channel.onmessage = (ev) => {
      if (ev.data && ev.data.type === 'change') {
        cache = null;
        load();
        notifyListeners();
      }
    };
  }
  window.addEventListener('storage', (ev) => {
    if (ev.key === STORAGE_KEY) {
      cache = null;
      load();
      notifyListeners();
    }
  });

  function onChange(cb) {
    listeners.add(cb);
    return () => listeners.delete(cb);
  }

  // ---- Settings ----
  function getSettings() {
    return structuredClone(load().settings);
  }
  function saveSettings(partial) {
    load();
    cache.settings = { ...cache.settings, ...partial };
    persist();
    return getSettings();
  }

  // ---- Generic list helpers (prayers / lessons / announcements / halacha) ----
  function getList(name) {
    return structuredClone(load()[name] || []);
  }
  function addItem(name, item) {
    load();
    const record = { ...item, id: item.id || uid(), createdAt: Date.now() };
    cache[name].push(record);
    persist();
    return record;
  }
  function updateItem(name, id, patch) {
    load();
    const idx = cache[name].findIndex((it) => it.id === id);
    if (idx === -1) return null;
    cache[name][idx] = { ...cache[name][idx], ...patch };
    persist();
    return cache[name][idx];
  }
  function deleteItem(name, id) {
    load();
    cache[name] = cache[name].filter((it) => it.id !== id);
    persist();
  }
  function reorderList(name, orderedIds) {
    load();
    const byId = new Map(cache[name].map((it) => [it.id, it]));
    cache[name] = orderedIds.map((id) => byId.get(id)).filter(Boolean);
    persist();
  }

  // ---- Announcements: drop expired ones automatically ----
  function getActiveAnnouncements() {
    const now = Date.now();
    const all = getList('announcements');
    return all.filter((a) => !a.expiresAt || a.expiresAt > now);
  }

  // ---- Auth (client-side gate for the admin panel; NOT real security) ----
  function hasAuth() {
    return !!load().auth;
  }
  function setAuth(salt, hash) {
    load();
    cache.auth = { salt, hash };
    persist();
  }
  function getAuth() {
    return load().auth ? structuredClone(load().auth) : null;
  }

  // ---- Backup / restore ----
  function exportJSON() {
    return JSON.stringify(load(), null, 2);
  }
  function importJSON(json) {
    const parsed = JSON.parse(json);
    cache = deepMerge(DEFAULT_DATA, parsed);
    persist();
  }

  return {
    getSettings,
    saveSettings,
    getList,
    addItem,
    updateItem,
    deleteItem,
    reorderList,
    getActiveAnnouncements,
    hasAuth,
    setAuth,
    getAuth,
    exportJSON,
    importJSON,
    onChange,
  };
})();
