# מסך בית הכנסת

מערכת בת שני חלקים, מחוברת ל-Firebase (מסד נתונים חי + התחברות + אחסון
תמונות), כך שכל שינוי שהגבאי עושה בטלפון מופיע מיד בטלוויזיה - בלי צורך
שהם יהיו על אותו מכשיר:

- **`index.html`** - מסך התצוגה, לפתיחה במסך מלא בטלוויזיה/מסך גדול.
- **`admin.html`** - לוח ניהול לגבאי, לכניסה מהטלפון.

## מה כלול בגרסה הזו

שעון ותאריך עברי, פרשת השבוע וחגים, זמני היום ושבת (מ-Hebcal), זמני
תפילות (קבועים או יחסיים לזמן הלכתי), שיעורים, הודעות עם תמונה ותפוגה
אוטומטית, כניסת גבאי מאובטחת עם Firebase Authentication, ועדכון חי בין
המכשירים דרך Firestore.

## הקמה - שלב אחר שלב

### 1. יצירת פרויקט Firebase

1. נכנסים ל-<https://console.firebase.google.com> עם חשבון Google ולוחצים
   "הוספת פרויקט" (Add project).
2. נותנים שם לפרויקט (למשל `synagogue-display`), אפשר לכבות את Google
   Analytics (לא נדרש).
3. בתפריט הפרויקט: **Build → Firestore Database → Create database** -
   לבחור "Start in production mode" ולבחור אזור (region) קרוב, למשל
   `eur3 (europe-west)`.
4. **Build → Authentication → Get started → Sign-in method → Email/Password
   → Enable**.
5. **Build → Authentication → Users → Add user** - כאן יוצרים את המשתמש של
   הגבאי (אימייל + סיסמה). זו הדרך היחידה ליצור גבאי - אין טופס הרשמה
   פתוח באתר, מתוך שיקול אבטחה.
6. **Build → Storage → Get started** - להפעלת אחסון לתמונות (לוגו,
   הודעות).
7. בתפריט השיניים **Project settings → General → Your apps**, לוחצים על
   סמל ה-Web `</>`, נותנים שם לאפליקציה (לא חייבים לסמן Hosting כרגע), ואז
   מעתיקים את אובייקט ה-`firebaseConfig` שמוצג (`apiKey`, `authDomain`,
   `projectId`, `storageBucket`, `messagingSenderId`, `appId`).
8. את פרטי ה-`firebaseConfig` וה-`projectId` שולחים למי שמריץ את הפריסה
   (או ממלאים בעצמכם ב-`js/firebase-config.js` וב-`.firebaserc`).

זהו - כל זה חינמי (תוכנית Spark), ומספיק בהרבה לתעבורה של בית כנסת בודד.
אין צורך בכרטיס אשראי בשלב הזה.

### 2. חוקי אבטחה (Security Rules)

הקבצים `firestore.rules` ו-`storage.rules` שבתיקייה כבר מוגדרים נכון:
קריאה פתוחה לכולם (כדי שהמסך בטלוויזיה יעבוד בלי התחברות), וכתיבה מותרת
רק למי שמחובר (הגבאי). הם מועלים אוטומטית בפריסה (ראו שלב 4).

### 3. חיבור הקוד לפרויקט

- ממלאים את הערכים האמיתיים בקובץ `js/firebase-config.js` במקום
  `REPLACE_ME`.
- ממלאים את מזהה הפרויקט (`projectId`) בקובץ `.firebaserc` במקום
  `REPLACE_WITH_PROJECT_ID`.

### 4. פריסה לאוויר (Firebase Hosting)

```bash
npm install -g firebase-tools
firebase login          # פותח דפדפן להתחברות לחשבון Google שלכם
cd synagogue-display
firebase deploy
```

בסיום התהליך תופיע כתובת אמיתיות שהאתר עובד בה, בדרך כלל:
`https://<project-id>.web.app`

**אם רוצים שמישהו אחר (כמו סוכן קוד מרוחק) יריץ את הפריסה במקומכם**, בלי
לשתף אותו בסיסמת Google שלכם:

```bash
firebase login:ci
```

הפקודה תפתח דפדפן להתחברות, ובסוף תדפיס טוקן חד-פעמי (מחרוזת ארוכה).
שולחים את הטוקן הזה, והוא מריץ עם:

```bash
firebase deploy --token "הטוקן שקיבלתם"
```

הטוקן הזה שווה-ערך להרשאת גישה לפרויקט - מתייחסים אליו כמו לסיסמה, ואפשר
לבטל אותו בכל רגע דרך הגדרות האבטחה של חשבון ה-Google (Third-party access).

## איך מריצים מקומית (לבדיקות)

```bash
cd synagogue-display
python3 -m http.server 8080
```

ואז פותחים `http://localhost:8080/index.html` ו-`http://localhost:8080/admin.html`.

## מבנה הנתונים ב-Firestore

```
synagogues/main                         { settings: {...} }
synagogues/main/prayers/{id}
synagogues/main/lessons/{id}
synagogues/main/announcements/{id}
synagogues/main/halacha/{id}             (טרם ממומש בממשק)
```

כל הגישה לנתונים עוברת דרך `js/store.js` - קובץ אחד עם API קבוע
(`getSettings`, `saveSettings`, `getList`, `addItem`, `updateItem`,
`deleteItem`, `onChange`, `signIn`, `uploadImage`...) שגם `display.js` וגם
`admin.js` משתמשים בו, כך שאפשר להרחיב את המערכת (בתי כנסת נוספים, שדות
נוספים) בלי לשנות את שאר הקוד.

## הלכה יומית

עדיין לא ממומש בממשק. יש להוסיף מסמכים תחת `halacha/{id}` (טקסט קצר +
נושא + שם הרב שאישר), ולהימנע מהעתקת ספר הלכה שלם ללא רשות.

## מקור הנתונים ההלכתיים

זמנים הלכתיים, תאריך עברי, פרשת השבוע וחגים מגיעים מה-API הציבורי של
[Hebcal](https://www.hebcal.com), לפי קו רוחב/קו אורך שמוגדרים בהגדרות
בית הכנסת (לשונית "הגדרות" בלוח הניהול). חשוב לוודא מול רב בית הכנסת את
המנהג המדויק (דקות לפני שקיעה, שיטת צאת הכוכבים).

## עלויות

תוכנית Spark (החינמית) של Firebase כוללת נדיבות שמספיקה בהרבה למסך אחד
של בית כנסת: 50,000 קריאות Firestore ליום, 1GB אחסון קבצים, ו-10GB
תעבורת Hosting לחודש. אין צורך לשדרג לתוכנית בתשלום (Blaze) אלא אם רוצים
דומיין מותאם אישית עם כמות תעבורה גדולה במיוחד, או להוסיף בתי כנסת רבים
נוספים באותו פרויקט.
