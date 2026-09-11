const apiKeyEl = document.getElementById('apiKey');
const modelEl = document.getElementById('model');
const defaultLangEl = document.getElementById('defaultLang');
const saveBtn = document.getElementById('saveBtn');
const savedEl = document.getElementById('saved');

async function load() {
  const cfg = await chrome.storage.local.get(['smtApiKey', 'smtModel', 'smtTargetLang']);
  if (cfg.smtApiKey) apiKeyEl.value = cfg.smtApiKey;
  modelEl.value = cfg.smtModel || 'claude-haiku-4-5-20251001';
  defaultLangEl.value = cfg.smtTargetLang || 'he';
}

saveBtn.addEventListener('click', async () => {
  await chrome.storage.local.set({
    smtApiKey: apiKeyEl.value.trim(),
    smtModel: modelEl.value,
    smtTargetLang: defaultLangEl.value
  });
  savedEl.textContent = 'נשמר ✓';
  setTimeout(() => { savedEl.textContent = ''; }, 2000);
});

load();
