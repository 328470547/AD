/*
 * Data layer for the synagogue system, backed by Firebase (Firestore +
 * Authentication + Storage). This is the real, always-on backend: the
 * gabbai's phone and the TV display both read/write the same cloud
 * document, live, over `onSnapshot`.
 *
 * Firestore layout:
 *   synagogues/{SYNAGOGUE_ID}                    -> { settings: {...} }
 *   synagogues/{SYNAGOGUE_ID}/prayers/{id}
 *   synagogues/{SYNAGOGUE_ID}/lessons/{id}
 *   synagogues/{SYNAGOGUE_ID}/announcements/{id}
 *   synagogues/{SYNAGOGUE_ID}/halacha/{id}
 *
 * Every UI file (display.js / admin.js) talks to the data only through the
 * exported `Store` object below - see README.md for the security rules
 * that keep reads public (for the TV screen) and writes gated to signed-in
 * gabbaim (Firebase Authentication, Email/Password).
 */

import { firebaseConfig, SYNAGOGUE_ID } from './firebase-config.js';
import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-app.js';
import {
  initializeFirestore,
  persistentLocalCache,
  persistentSingleTabManager,
  doc,
  collection,
  onSnapshot,
  setDoc,
  addDoc,
  updateDoc,
  deleteDoc,
} from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-firestore.js';
import {
  getAuth,
  signInWithEmailAndPassword,
  signOut,
  onAuthStateChanged,
} from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-auth.js';
import {
  getStorage,
  ref as storageRef,
  uploadBytes,
  getDownloadURL,
} from 'https://www.gstatic.com/firebasejs/10.14.1/firebase-storage.js';

const DEFAULT_SETTINGS = {
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
};

const app = initializeApp(firebaseConfig);
const db = initializeFirestore(app, {
  localCache: persistentLocalCache({ tabManager: persistentSingleTabManager() }),
});
const auth = getAuth(app);
const storage = getStorage(app);

const synRef = doc(db, 'synagogues', SYNAGOGUE_ID);
const listRef = (name) => collection(db, 'synagogues', SYNAGOGUE_ID, name);

let settingsCache = { ...DEFAULT_SETTINGS };
let listsCache = { prayers: [], lessons: [], announcements: [], halacha: [] };
const changeListeners = new Set();
const authListeners = new Set();

function notifyChange() {
  for (const cb of changeListeners) {
    try {
      cb();
    } catch (e) {
      console.error('Store listener error', e);
    }
  }
}

onSnapshot(
  synRef,
  (snap) => {
    settingsCache = { ...DEFAULT_SETTINGS, ...(snap.data()?.settings || {}) };
    notifyChange();
  },
  (err) => console.error('Store: settings snapshot error', err)
);

for (const name of Object.keys(listsCache)) {
  onSnapshot(
    listRef(name),
    (qs) => {
      listsCache[name] = qs.docs.map((d) => ({ id: d.id, ...d.data() }));
      notifyChange();
    },
    (err) => console.error(`Store: ${name} snapshot error`, err)
  );
}

onAuthStateChanged(auth, (user) => {
  for (const cb of authListeners) cb(user);
});

// ---- Settings ----
function getSettings() {
  return { ...settingsCache };
}
function saveSettings(patch) {
  return setDoc(synRef, { settings: { ...settingsCache, ...patch } }, { merge: true });
}

// ---- Generic lists (prayers / lessons / announcements / halacha) ----
function getList(name) {
  return [...(listsCache[name] || [])];
}
function addItem(name, item) {
  return addDoc(listRef(name), { ...item, createdAt: Date.now() });
}
function updateItem(name, id, patch) {
  return updateDoc(doc(db, 'synagogues', SYNAGOGUE_ID, name, id), patch);
}
function deleteItem(name, id) {
  return deleteDoc(doc(db, 'synagogues', SYNAGOGUE_ID, name, id));
}

function getActiveAnnouncements() {
  const now = Date.now();
  return getList('announcements').filter((a) => !a.expiresAt || a.expiresAt > now);
}

// ---- Auth (real Firebase Authentication - gabbai users are created from
// the Firebase console, see README.md) ----
function signIn(email, password) {
  return signInWithEmailAndPassword(auth, email, password);
}
function signOutUser() {
  return signOut(auth);
}
function onAuthChange(cb) {
  authListeners.add(cb);
  cb(auth.currentUser);
  return () => authListeners.delete(cb);
}
function getCurrentUser() {
  return auth.currentUser;
}

// ---- Images (logo / announcement photos) go to Firebase Storage; only
// the resulting https URL is stored in Firestore. ----
async function uploadImage(file, folder) {
  const path = `${folder}/${Date.now()}_${file.name.replace(/[^a-zA-Z0-9._-]/g, '_')}`;
  const ref = storageRef(storage, path);
  await uploadBytes(ref, file);
  return getDownloadURL(ref);
}

function onChange(cb) {
  changeListeners.add(cb);
  return () => changeListeners.delete(cb);
}

export const Store = {
  getSettings,
  saveSettings,
  getList,
  addItem,
  updateItem,
  deleteItem,
  getActiveAnnouncements,
  onChange,
  signIn,
  signOutUser,
  onAuthChange,
  getCurrentUser,
  uploadImage,
};
