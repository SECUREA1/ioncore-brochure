(() => {
  const UNLOCK_KEY = 'ioncore-bom-unlocked';
  const PASSWORD = 'brasstax';
  const KEYWORDS = /(bill of materials|\bbom\b|parts list|parts\s*&\s*bom|full parts|materials and partner-ready|parts and labor breakdown|engineering bom)/i;
  const CANDIDATE_SELECTORS = [
    'section', 'article', 'div', 'table', 'ul', 'ol'
  ].join(',');

  function isUnlocked() {
    return sessionStorage.getItem(UNLOCK_KEY) === '1';
  }

  function makeStyles() {
    const style = document.createElement('style');
    style.textContent = `
      .bom-fog-mask {
        position: relative !important;
        filter: blur(12px) saturate(0.4) brightness(0.55);
        pointer-events: none;
        user-select: none;
      }
      .bom-fog-mask::after {
        content: "Restricted: BOM / parts list hidden";
        position: absolute;
        inset: 0;
        display: grid;
        place-items: center;
        text-align: center;
        font: 700 1rem/1.4 Montserrat, Arial, sans-serif;
        letter-spacing: 0.04em;
        color: #fff;
        background: rgba(7, 10, 16, 0.78);
        text-transform: uppercase;
        pointer-events: none;
      }
      .bom-unlock-btn {
        position: fixed;
        right: 14px;
        bottom: 14px;
        z-index: 99999;
        border: 1px solid rgba(255,255,255,0.22);
        background: rgba(9,12,18,0.85);
        color: #f6f7f9;
        border-radius: 999px;
        padding: 0.55rem 0.85rem;
        cursor: pointer;
        font: 600 0.8rem/1 Montserrat, Arial, sans-serif;
      }
    `;
    document.head.appendChild(style);
  }

  function targetElements() {
    return [...document.querySelectorAll(CANDIDATE_SELECTORS)].filter((el) => {
      if (el.classList.contains('bom-unlock-btn')) return false;
      const text = (el.textContent || '').replace(/\s+/g, ' ').trim();
      if (!text || text.length > 10000) return false;
      if (!KEYWORDS.test(text)) return false;
      return true;
    });
  }

  function applyMask() {
    if (isUnlocked()) return;
    targetElements().forEach((el) => el.classList.add('bom-fog-mask'));
  }

  function clearMask() {
    document.querySelectorAll('.bom-fog-mask').forEach((el) => el.classList.remove('bom-fog-mask'));
  }

  function addUnlockControl() {
    const btn = document.createElement('button');
    btn.className = 'bom-unlock-btn';
    btn.type = 'button';
    btn.textContent = isUnlocked() ? 'BOM Unlocked' : 'Unlock BOM';
    btn.setAttribute('aria-label', 'Unlock restricted BOM and parts sections');
    btn.addEventListener('click', () => {
      if (isUnlocked()) {
        sessionStorage.removeItem(UNLOCK_KEY);
        btn.textContent = 'Unlock BOM';
        applyMask();
        return;
      }
      const input = window.prompt('Enter BOM access password');
      if (!input) return;
      if (input.trim().toLowerCase() === PASSWORD) {
        sessionStorage.setItem(UNLOCK_KEY, '1');
        clearMask();
        btn.textContent = 'BOM Unlocked';
      } else {
        window.alert('Incorrect password.');
      }
    });
    document.body.appendChild(btn);
  }

  document.addEventListener('DOMContentLoaded', () => {
    makeStyles();
    applyMask();
    addUnlockControl();
  });
})();
