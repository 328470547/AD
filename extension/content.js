// Smart Context Translator - content script
// Design goals:
//  - Never touch DOM structure/attributes (links, bold, classes) — only swap text.
//  - Translate whole sentences/blocks (not word-by-word) so word order stays correct.
//  - Set dir/lang per translated block so the browser's bidi algorithm renders
//    mixed RTL/LTR content correctly (this is the #1 fix for "text gets scrambled").
//  - Fully revertible: original DOM nodes are kept alive in memory, never destroyed.

(() => {
  if (window.__smtInjected) return;
  window.__smtInjected = true;

  const SKIP_TAGS = new Set([
    'SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'SVG', 'MATH', 'CODE', 'PRE',
    'TEXTAREA', 'INPUT', 'SELECT', 'OPTION', 'IFRAME', 'CANVAS', 'VIDEO',
    'AUDIO', 'OBJECT', 'EMBED'
  ]);

  const RTL_LANGS = new Set(['he', 'ar', 'fa', 'ur', 'yi', 'iw']);
  const LETTER_RE = /\p{L}/u;
  const TOKEN_RE = /⟦(\d+)⟧/g;

  let units = [];
  let unitCounter = 0;
  let originalTitle = null;
  let translated = false;
  let inProgress = false;
  let badgeEl = null;

  function isRtlLang(code) {
    return RTL_LANGS.has((code || '').toLowerCase().split('-')[0]);
  }

  function shouldSkip(el) {
    if (!(el instanceof Element)) return true;
    if (SKIP_TAGS.has(el.tagName)) return true;
    if (el.isContentEditable) return true;
    if (el.hasAttribute('data-smt-unit')) return true;
    if (el.translate === false) return true;
    if (el.closest && el.closest('[translate="no"], .notranslate')) return true;
    return false;
  }

  function getDirectText(el) {
    let text = '';
    for (const node of el.childNodes) {
      if (node.nodeType === Node.TEXT_NODE) text += node.data;
    }
    return text;
  }

  function createUnit(el) {
    const originalChildNodes = Array.from(el.childNodes);
    const tokens = {};
    let sourceString = '';
    for (const node of originalChildNodes) {
      if (node.nodeType === Node.TEXT_NODE) {
        sourceString += node.data;
      } else {
        const id = String(Object.keys(tokens).length);
        tokens[id] = node;
        sourceString += `⟦${id}⟧`;
      }
    }
    return {
      id: unitCounter++,
      element: el,
      originalChildNodes,
      tokens,
      sourceString,
      translatedString: null
    };
  }

  function scan(root) {
    const found = [];
    function walk(el) {
      if (shouldSkip(el)) return;
      const directText = getDirectText(el);
      if (LETTER_RE.test(directText)) {
        found.push(createUnit(el));
      }
      for (const child of Array.from(el.children)) walk(child);
    }
    walk(root);
    return found;
  }

  function rebuildUnit(unit) {
    if (unit.translatedString == null) return;
    const parts = unit.translatedString.split(TOKEN_RE);
    // split() with a capturing group alternates: text, tokenId, text, tokenId, ...
    const newChildren = [];
    for (let i = 0; i < parts.length; i++) {
      if (i % 2 === 0) {
        if (parts[i]) newChildren.push(document.createTextNode(parts[i]));
      } else {
        const node = unit.tokens[parts[i]];
        if (node) newChildren.push(node);
      }
    }
    // Any token that didn't survive translation (model dropped it) gets appended
    // at the end so we never silently lose page content (links, images, etc.)
    const usedIds = new Set(parts.filter((_, i) => i % 2 === 1));
    for (const id of Object.keys(unit.tokens)) {
      if (!usedIds.has(id)) newChildren.push(unit.tokens[id]);
    }
    unit.element.replaceChildren(...newChildren);
  }

  function revertUnit(unit) {
    unit.element.replaceChildren(...unit.originalChildNodes);
    unit.element.removeAttribute('data-smt-unit');
    unit.element.removeAttribute('dir');
    unit.element.removeAttribute('lang');
  }

  function detectPageLang() {
    const htmlLang = document.documentElement.lang;
    if (htmlLang) return htmlLang.split('-')[0].toLowerCase();
    const sample = document.body.innerText.slice(0, 2000);
    if (/[֐-׿]/.test(sample)) return 'he';
    if (/[؀-ۿ]/.test(sample)) return 'ar';
    if (/[Ѐ-ӿ]/.test(sample)) return 'ru';
    if (/[一-鿿]/.test(sample)) return 'zh';
    if (/[぀-ヿ]/.test(sample)) return 'ja';
    if (/[가-힯]/.test(sample)) return 'ko';
    return 'en';
  }

  function showBadge(text) {
    if (!badgeEl) {
      badgeEl = document.createElement('div');
      badgeEl.setAttribute('data-smt-skip', '1');
      badgeEl.translate = false;
      badgeEl.className = 'smt-badge notranslate';
      document.documentElement.appendChild(badgeEl);
    }
    badgeEl.textContent = text;
    badgeEl.classList.add('smt-badge-visible');
  }

  function hideBadge(delay = 1800) {
    if (!badgeEl) return;
    setTimeout(() => badgeEl && badgeEl.classList.remove('smt-badge-visible'), delay);
  }

  function chunkUnits(list, maxChars, maxItems) {
    const chunks = [];
    let cur = [];
    let curLen = 0;
    for (const u of list) {
      const len = u.sourceString.length;
      if (cur.length && (curLen + len > maxChars || cur.length >= maxItems)) {
        chunks.push(cur);
        cur = [];
        curLen = 0;
      }
      cur.push(u);
      curLen += len;
    }
    if (cur.length) chunks.push(cur);
    return chunks;
  }

  async function translateChunk(chunk, targetLang, sourceLang, pageContext) {
    const items = chunk.map(u => u.sourceString);
    const resp = await chrome.runtime.sendMessage({
      type: 'smt-translate-batch',
      payload: { items, targetLang, sourceLang, pageContext }
    });
    if (!resp || !resp.success) {
      throw new Error((resp && resp.error) || 'Unknown translation error');
    }
    return resp.translations;
  }

  async function translatePage(targetLang) {
    if (inProgress) return { ok: false, error: 'already-in-progress' };
    inProgress = true;
    try {
      if (translated) {
        // re-translating to a different language: revert first for a clean pass
        revertPage();
      }
      units = scan(document.body);
      const sourceLang = detectPageLang();
      const pageContext = {
        title: document.title,
        description: (document.querySelector('meta[name="description"]') || {}).content || ''
      };

      if (!units.length) {
        inProgress = false;
        return { ok: true, translatedUnits: 0 };
      }

      showBadge(`מתרגם… 0/${units.length}`);

      const chunks = chunkUnits(units, 6000, 60);
      let done = 0;
      let failedChunks = 0;

      const CONCURRENCY = 3;
      let idx = 0;
      async function worker() {
        while (idx < chunks.length) {
          const myIdx = idx++;
          const chunk = chunks[myIdx];
          try {
            const translations = await translateChunk(chunk, targetLang, sourceLang, pageContext);
            chunk.forEach((u, i) => {
              u.translatedString = translations[i] != null ? String(translations[i]) : u.sourceString;
              u.element.setAttribute('data-smt-unit', '1');
              u.element.setAttribute('dir', isRtlLang(targetLang) ? 'rtl' : 'ltr');
              u.element.setAttribute('lang', targetLang);
              rebuildUnit(u);
            });
          } catch (e) {
            failedChunks++;
            console.warn('[Smart Translator] chunk failed:', e);
          }
          done += chunk.length;
          showBadge(`מתרגם… ${Math.min(done, units.length)}/${units.length}`);
        }
      }
      await Promise.all(Array.from({ length: Math.min(CONCURRENCY, chunks.length) }, worker));

      // translate the tab title too
      if (originalTitle == null) originalTitle = document.title;
      try {
        const [titleTranslation] = await translateChunk(
          [{ sourceString: document.title }],
          targetLang, sourceLang, pageContext
        );
        if (titleTranslation) document.title = titleTranslation;
      } catch (e) { /* non-critical */ }

      document.documentElement.setAttribute('data-smt-active-lang', targetLang);
      translated = true;
      if (failedChunks) {
        showBadge(`תורגם עם שגיאות (${failedChunks} חלקים נכשלו)`);
      } else {
        showBadge('הדף תורגם ✓');
      }
      hideBadge();
      return { ok: true, translatedUnits: units.length, failedChunks };
    } finally {
      inProgress = false;
    }
  }

  function revertPage() {
    for (const u of units) revertUnit(u);
    units = [];
    if (originalTitle != null) {
      document.title = originalTitle;
      originalTitle = null;
    }
    document.documentElement.removeAttribute('data-smt-active-lang');
    translated = false;
    if (badgeEl) {
      badgeEl.remove();
      badgeEl = null;
    }
    return { ok: true };
  }

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (!msg || msg.target !== 'smt-content') return;
    if (msg.action === 'translate') {
      translatePage(msg.targetLang).then(sendResponse);
      return true;
    }
    if (msg.action === 'revert') {
      sendResponse(revertPage());
      return false;
    }
    if (msg.action === 'status') {
      sendResponse({ translated, inProgress, unitCount: units.length, detectedLang: detectPageLang() });
      return false;
    }
  });

  // Optional auto-translate: only runs if the user enabled it and the page
  // language differs from their configured target language.
  chrome.storage.local.get(['smtAutoTranslate', 'smtTargetLang'], (cfg) => {
    if (!cfg.smtAutoTranslate || !cfg.smtTargetLang) return;
    const pageLang = detectPageLang();
    if (pageLang === cfg.smtTargetLang) return;
    // give the page a moment to finish rendering dynamic content
    setTimeout(() => translatePage(cfg.smtTargetLang), 1200);
  });
})();
