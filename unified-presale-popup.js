(() => {
  if (document.getElementById('ioncore-presale-popup')) return;

  const style = document.createElement('style');
  style.textContent = `
    #ioncore-presale-popup {
      position: fixed;
      right: clamp(14px, 2vw, 28px);
      bottom: clamp(14px, 2vw, 28px);
      z-index: 2147483000;
      width: min(390px, calc(100vw - 28px));
      color: #f8fbff;
      font-family: Montserrat, Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    #ioncore-presale-popup * { box-sizing: border-box; }
    .ioncore-presale-card {
      position: relative;
      display: grid;
      gap: 14px;
      overflow: hidden;
      padding: 20px;
      border: 1px solid rgba(255, 214, 102, 0.44);
      border-radius: 26px;
      background:
        radial-gradient(circle at 18% 0%, rgba(255, 214, 102, 0.22), transparent 32%),
        radial-gradient(circle at 94% 16%, rgba(73, 210, 255, 0.16), transparent 30%),
        linear-gradient(145deg, rgba(5, 9, 18, 0.97), rgba(15, 24, 41, 0.96) 52%, rgba(13, 39, 31, 0.95));
      box-shadow: 0 24px 80px rgba(0, 0, 0, 0.52), 0 0 54px rgba(255, 214, 102, 0.16);
      backdrop-filter: blur(18px);
    }
    .ioncore-presale-card::before {
      content: "";
      position: absolute;
      inset: 0;
      pointer-events: none;
      background: linear-gradient(115deg, rgba(255, 255, 255, 0.16), transparent 24%, transparent 70%, rgba(106, 255, 59, 0.10));
    }
    .ioncore-presale-card > * { position: relative; z-index: 1; }
    .ioncore-presale-topline {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .ioncore-presale-kicker {
      color: #ffd666;
      font-size: 0.7rem;
      font-weight: 900;
      letter-spacing: 0.17em;
      text-transform: uppercase;
    }
    .ioncore-presale-badge {
      border: 1px solid rgba(106, 255, 59, 0.34);
      border-radius: 999px;
      padding: 6px 9px;
      background: rgba(106, 255, 59, 0.10);
      color: #baff9f;
      font-size: 0.64rem;
      font-weight: 900;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      white-space: nowrap;
    }
    .ioncore-presale-title {
      margin: 0;
      color: #ffffff;
      font-size: clamp(1.08rem, 2.2vw, 1.35rem);
      line-height: 1.18;
      font-weight: 950;
      letter-spacing: -0.02em;
    }
    .ioncore-presale-copy {
      margin: 0;
      color: rgba(235, 244, 255, 0.86);
      font-size: 0.88rem;
      line-height: 1.55;
    }
    .ioncore-presale-points {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
    }
    .ioncore-presale-point {
      min-height: 58px;
      border: 1px solid rgba(255, 255, 255, 0.10);
      border-radius: 16px;
      padding: 10px;
      background: rgba(255, 255, 255, 0.055);
    }
    .ioncore-presale-point strong {
      display: block;
      color: #ffffff;
      font-size: 0.72rem;
      line-height: 1.2;
      text-transform: uppercase;
    }
    .ioncore-presale-point span {
      display: block;
      margin-top: 4px;
      color: rgba(235, 244, 255, 0.68);
      font-size: 0.66rem;
      line-height: 1.25;
    }
    .ioncore-presale-actions,
    .ioncore-presale-tab-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .ioncore-presale-link,
    .ioncore-presale-tab-link {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 12px 17px;
      border-radius: 999px;
      background: linear-gradient(135deg, #ffd666, #6aff3b);
      color: #061016 !important;
      font-size: 0.84rem;
      font-weight: 950;
      text-decoration: none;
      box-shadow: 0 14px 36px rgba(255, 214, 102, 0.24), 0 10px 30px rgba(106, 255, 59, 0.22);
    }
    .ioncore-presale-link--secondary,
    .ioncore-presale-tab-link--secondary {
      background: linear-gradient(135deg, #49d2ff, #9ffcff);
      box-shadow: 0 14px 36px rgba(73, 210, 255, 0.20), 0 10px 30px rgba(159, 252, 255, 0.16);
    }
    .ioncore-presale-toggle {
      border: 1px solid rgba(255, 255, 255, 0.18);
      border-radius: 999px;
      padding: 10px 13px;
      background: rgba(255, 255, 255, 0.075);
      color: #ffffff;
      cursor: pointer;
      font: inherit;
      font-size: 0.79rem;
      font-weight: 850;
    }
    #ioncore-presale-popup.is-collapsed { width: min(390px, calc(100vw - 28px)); }
    #ioncore-presale-popup.is-collapsed .ioncore-presale-card { display: none; }
    #ioncore-presale-popup:not(.is-collapsed) .ioncore-presale-tab { display: none; }
    .ioncore-presale-tab {
      display: grid;
      gap: 10px;
      border: 1px solid rgba(255, 214, 102, 0.58);
      border-radius: 999px;
      padding: 12px 16px;
      background: linear-gradient(135deg, rgba(5, 9, 18, 0.97), rgba(18, 37, 32, 0.97));
      color: #ffffff;
      box-shadow: 0 14px 44px rgba(0, 0, 0, 0.40), 0 0 34px rgba(255, 214, 102, 0.18);
      font: inherit;
      font-size: 0.82rem;
      font-weight: 950;
    }
    .ioncore-presale-tab-label {
      display: flex;
      align-items: center;
      gap: 9px;
    }
    .ioncore-presale-tab-label::before {
      content: "";
      width: 9px;
      height: 9px;
      border-radius: 50%;
      background: #6aff3b;
      box-shadow: 0 0 18px rgba(106, 255, 59, 0.9);
    }
    .ioncore-presale-tab-link { padding: 10px 13px; font-size: 0.76rem; }
    .ioncore-presale-tab-expand {
      border: 1px solid rgba(255, 255, 255, 0.18);
      border-radius: 999px;
      padding: 10px 13px;
      background: rgba(255, 255, 255, 0.075);
      color: #ffffff;
      cursor: pointer;
      font: inherit;
      font-size: 0.76rem;
      font-weight: 850;
    }
    @media (max-width: 420px) {
      .ioncore-presale-points { grid-template-columns: 1fr; }
      .ioncore-presale-topline { align-items: flex-start; flex-direction: column; }
    }
  `;

  const popup = document.createElement('aside');
  popup.id = 'ioncore-presale-popup';
  popup.setAttribute('aria-label', 'Sales and prefunding launch page');
  popup.innerHTML = `
    <div class="ioncore-presale-card">
      <div class="ioncore-presale-topline">
        <div class="ioncore-presale-kicker">Professional launch tile</div>
        <div class="ioncore-presale-badge">Sales + Prefunding</div>
      </div>
      <h2 class="ioncore-presale-title">IonCore Sales &amp; Prefunding Launch</h2>
      <p class="ioncore-presale-copy">Open the finalized investment, product reservation, and launch overview from any page.</p>
      <div class="ioncore-presale-points" aria-label="Launch page highlights">
        <div class="ioncore-presale-point"><strong>Raise</strong><span>Investor-ready overview</span></div>
        <div class="ioncore-presale-point"><strong>Reserve</strong><span>Premium presale path</span></div>
        <div class="ioncore-presale-point"><strong>Launch</strong><span>Unified sales story</span></div>
      </div>
      <div class="ioncore-presale-actions">
        <a class="ioncore-presale-link ioncore-presale-link--secondary" href="/ambassador-partner-grants.html">Ambassador page</a>
        <a class="ioncore-presale-link" href="/unified-fundraising-presale.html">Sales page</a>
        <button class="ioncore-presale-toggle" type="button" aria-expanded="true">Collapse tile</button>
      </div>
    </div>
    <div class="ioncore-presale-tab" aria-label="IonCore quick links">
      <div class="ioncore-presale-tab-label">IonCore quick links</div>
      <div class="ioncore-presale-tab-actions">
        <a class="ioncore-presale-tab-link ioncore-presale-tab-link--secondary" href="/ambassador-partner-grants.html">Ambassador</a>
        <a class="ioncore-presale-tab-link" href="/unified-fundraising-presale.html">Sales page</a>
        <button class="ioncore-presale-tab-expand" type="button" aria-expanded="false">Details</button>
      </div>
    </div>
  `;

  const setCollapsed = (collapsed) => {
    popup.classList.toggle('is-collapsed', collapsed);
    popup.querySelectorAll('button[aria-expanded]').forEach((button) => {
      button.setAttribute('aria-expanded', String(!collapsed));
    });
  };

  popup.querySelector('.ioncore-presale-toggle').addEventListener('click', () => setCollapsed(true));
  popup.querySelector('.ioncore-presale-tab-expand').addEventListener('click', () => setCollapsed(false));
  setCollapsed(true);

  document.head.appendChild(style);
  document.body.appendChild(popup);
})();
