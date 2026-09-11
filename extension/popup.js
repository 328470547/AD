const targetLangEl = document.getElementById('targetLang');
const autoTranslateEl = document.getElementById('autoTranslate');
const translateBtn = document.getElementById('translateBtn');
const revertBtn = document.getElementById('revertBtn');
const statusEl = document.getElementById('status');
const optionsLink = document.getElementById('optionsLink');

optionsLink.addEventListener('click', (e) => {
  e.preventDefault();
  chrome.runtime.openOptionsPage();
});

function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.classList.toggle('error', !!isError);
}

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

async function sendToContent(action, extra = {}) {
  const tab = await getActiveTab();
  if (!tab || !tab.id) throw new Error('no-active-tab');
  return chrome.tabs.sendMessage(tab.id, { target: 'smt-content', action, ...extra });
}

async function refreshStatus() {
  try {
    const status = await sendToContent('status');
    if (status) {
      revertBtn.disabled = !status.translated;
      if (status.inProgress) {
        translateBtn.disabled = true;
        setStatus('מתרגם את הדף…');
      } else {
        translateBtn.disabled = false;
        setStatus(status.translated ? `הדף מתורגם (${status.unitCount} חלקים).` : '');
      }
    }
  } catch (e) {
    // content script may not be present on special pages (chrome://, webstore, etc.)
    setStatus('לא ניתן לתרגם דף זה.', true);
    translateBtn.disabled = true;
    revertBtn.disabled = true;
  }
}

async function loadSettings() {
  const cfg = await chrome.storage.local.get(['smtTargetLang', 'smtAutoTranslate', 'smtApiKey']);
  targetLangEl.value = cfg.smtTargetLang || 'he';
  autoTranslateEl.checked = !!cfg.smtAutoTranslate;
  if (!cfg.smtApiKey) {
    setStatus('יש להזין מפתח API בהגדרות לפני התרגום.', true);
    translateBtn.disabled = true;
  }
}

targetLangEl.addEventListener('change', () => {
  chrome.storage.local.set({ smtTargetLang: targetLangEl.value });
});

autoTranslateEl.addEventListener('change', () => {
  chrome.storage.local.set({ smtAutoTranslate: autoTranslateEl.checked });
});

translateBtn.addEventListener('click', async () => {
  translateBtn.disabled = true;
  setStatus('מתרגם את הדף…');
  try {
    const cfg = await chrome.storage.local.get(['smtModel']);
    const result = await sendToContent('translate', { targetLang: targetLangEl.value, model: cfg.smtModel });
    if (result && result.ok) {
      revertBtn.disabled = false;
      setStatus(
        result.failedChunks
          ? `תורגם עם ${result.failedChunks} שגיאות חלקיות.`
          : `הושלם! תורגמו ${result.translatedUnits} חלקי טקסט.`
      );
    } else {
      setStatus('אירעה שגיאה בתרגום.', true);
    }
  } catch (e) {
    setStatus('שגיאה: ' + (e.message || e), true);
  } finally {
    translateBtn.disabled = false;
  }
});

revertBtn.addEventListener('click', async () => {
  try {
    await sendToContent('revert');
    revertBtn.disabled = true;
    setStatus('שוחזר הטקסט המקורי.');
  } catch (e) {
    setStatus('שגיאה בשחזור.', true);
  }
});

loadSettings().then(refreshStatus);
