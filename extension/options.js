const providerEl = document.getElementById('provider');
const blockAnthropic = document.getElementById('block-anthropic');
const blockGemini = document.getElementById('block-gemini');
const apiKeyAnthropicEl = document.getElementById('apiKeyAnthropic');
const apiKeyGeminiEl = document.getElementById('apiKeyGemini');
const modelAnthropicEl = document.getElementById('modelAnthropic');
const modelGeminiEl = document.getElementById('modelGemini');
const defaultLangEl = document.getElementById('defaultLang');
const saveBtn = document.getElementById('saveBtn');
const savedEl = document.getElementById('saved');

function showProviderBlock(provider) {
  blockAnthropic.classList.toggle('active', provider === 'anthropic');
  blockGemini.classList.toggle('active', provider === 'gemini');
}

providerEl.addEventListener('change', () => showProviderBlock(providerEl.value));

async function load() {
  const cfg = await chrome.storage.local.get([
    'smtProvider', 'smtApiKey', 'smtModel',
    'smtApiKeyGemini', 'smtModelGemini', 'smtTargetLang'
  ]);
  const provider = cfg.smtProvider || 'anthropic';
  providerEl.value = provider;
  showProviderBlock(provider);

  if (cfg.smtApiKey) apiKeyAnthropicEl.value = cfg.smtApiKey;
  modelAnthropicEl.value = cfg.smtModel || 'claude-haiku-4-5-20251001';

  if (cfg.smtApiKeyGemini) apiKeyGeminiEl.value = cfg.smtApiKeyGemini;
  modelGeminiEl.value = cfg.smtModelGemini || 'gemini-2.5-flash';

  defaultLangEl.value = cfg.smtTargetLang || 'he';
}

saveBtn.addEventListener('click', async () => {
  await chrome.storage.local.set({
    smtProvider: providerEl.value,
    smtApiKey: apiKeyAnthropicEl.value.trim(),
    smtModel: modelAnthropicEl.value,
    smtApiKeyGemini: apiKeyGeminiEl.value.trim(),
    smtModelGemini: modelGeminiEl.value,
    smtTargetLang: defaultLangEl.value
  });
  savedEl.textContent = 'נשמר ✓';
  setTimeout(() => { savedEl.textContent = ''; }, 2000);
});

load();
