/*
 * Fill this in with the config object Firebase gives you when you register
 * a Web App in the Firebase console (Project settings -> General -> Your apps).
 * These values are meant to be public (they are not secrets - access is
 * controlled by the Firestore/Storage security rules, not by hiding this
 * object), so it is fine that this file is committed to the repo.
 *
 * See README.md for the exact steps to get these values.
 */
export const firebaseConfig = {
  apiKey: 'REPLACE_ME',
  authDomain: 'REPLACE_ME.firebaseapp.com',
  projectId: 'REPLACE_ME',
  storageBucket: 'REPLACE_ME.appspot.com',
  messagingSenderId: 'REPLACE_ME',
  appId: 'REPLACE_ME',
};

// A single synagogue is served by this deployment for now (matches the
// synagogues/{synagogueId} Firestore layout planned for multi-site later).
export const SYNAGOGUE_ID = 'main';
