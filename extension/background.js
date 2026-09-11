// Smart Context Translator - background service worker
// Owns the only network call in the extension: relays batches of text to the
// Anthropic API for context-aware translation, keeping the API key out of
// every page's execution context.

const API_URL = 'https://api.anthropic.com/v1/messages';
const DEFAULT_MODEL = 'claude-haiku-4-5-20251001';

const LANG_NAMES = {
  he: 'Hebrew', ar: 'Arabic', en: 'English', ru: 'Russian', fr: 'French',
  es: 'Spanish', de: 'German', it: 'Italian', pt: 'Portuguese', nl: 'Dutch',
  pl: 'Polish', tr: 'Turkish', ja: 'Japanese', ko: 'Korean', zh: 'Chinese',
  hi: 'Hindi', fa: 'Persian', ur: 'Urdu', uk: 'Ukrainian', el: 'Greek',
  sv: 'Swedish', fi: 'Finnish', cs: 'Czech', ro: 'Romanian', hu: 'Hungarian',
  th: 'Thai', vi: 'Vietnamese', id: 'Indonesian'
};

function langName(code) {
  return LANG_NAMES[(code || '').toLowerCase()] || code;
}

function buildSystemPrompt(targetLang, sourceLang, pageContext) {
  const target = langName(targetLang);
  return [
    `You are an elite professional translator producing publication-quality ${target} translations of real webpage content.`,
    `Page title: "${pageContext.title || ''}". ${pageContext.description ? `Page description: "${pageContext.description}".` : ''}`,
    `The source language is probably ${langName(sourceLang)}, but detect the real language of each segment yourself if it differs.`,
    'You will receive a JSON array of text segments extracted from the page (one per DOM element). Return ONLY a JSON array of the same length, in the same order, containing the translation of each segment.',
    'Hard rules:',
    '1. Some segments contain placeholder tokens of the exact form ⟦N⟧ (N is a number). Keep every token character-for-character identical, never translate or alter the digits, and never drop one — but you MUST move each token to whatever position is grammatically correct in the translated sentence for the target language, even if that position differs from the source.',
    '2. Translate the full meaning and intent, not word-by-word — use correct target-language grammar, word order, idiom and register, using the page title/description as context to disambiguate ambiguous terms.',
    '3. Do not translate: proper nouns without a standard localized form, code, URLs, email addresses, and numbers/units (convert only if the target locale uses a different numbering convention).',
    '4. Preserve the original tone (formal/casual/technical/marketing).',
    '5. If a segment is empty, purely numeric/symbolic, or already in the target language, return it unchanged.',
    '6. Output strictly valid JSON: a single array of strings. No markdown fences, no commentary, no keys, nothing else.'
  ].join('\n');
}

function extractJsonArray(text) {
  let cleaned = text.trim();
  cleaned = cleaned.replace(/^```(?:json)?\s*/i, '').replace(/```\s*$/i, '').trim();
  const start = cleaned.indexOf('[');
  const end = cleaned.lastIndexOf(']');
  if (start === -1 || end === -1 || end < start) {
    throw new Error('Model response did not contain a JSON array');
  }
  return JSON.parse(cleaned.slice(start, end + 1));
}

async function callAnthropic({ items, targetLang, sourceLang, pageContext, model }) {
  const { smtApiKey } = await chrome.storage.local.get(['smtApiKey']);
  if (!smtApiKey) {
    throw new Error('missing-api-key');
  }
  const systemPrompt = buildSystemPrompt(targetLang, sourceLang, pageContext);
  const userPrompt = JSON.stringify(items);
  const estimatedTokens = Math.min(8000, Math.max(512, Math.ceil(userPrompt.length * 1.8)));

  const res = await fetch(API_URL, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-api-key': smtApiKey,
      'anthropic-version': '2023-06-01',
      'anthropic-dangerous-direct-browser-access': 'true'
    },
    body: JSON.stringify({
      model: model || DEFAULT_MODEL,
      max_tokens: estimatedTokens,
      system: systemPrompt,
      messages: [{ role: 'user', content: userPrompt }]
    })
  });

  if (!res.ok) {
    const body = await res.text().catch(() => '');
    let message = `API error ${res.status}`;
    try {
      const parsed = JSON.parse(body);
      if (parsed && parsed.error && parsed.error.message) message = parsed.error.message;
    } catch (_) { /* ignore */ }
    throw new Error(message);
  }

  const data = await res.json();
  const text = (data.content || []).map(b => b.text || '').join('');
  const translations = extractJsonArray(text);
  if (!Array.isArray(translations) || translations.length !== items.length) {
    throw new Error('Translation count mismatch from model response');
  }
  return translations;
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (!msg || msg.type !== 'smt-translate-batch') return;
  callAnthropic(msg.payload)
    .then(translations => sendResponse({ success: true, translations }))
    .catch(err => sendResponse({ success: false, error: err.message || String(err) }));
  return true; // keep the message channel open for the async response
});
