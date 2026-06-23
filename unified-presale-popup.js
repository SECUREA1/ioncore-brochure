(() => {
  if (document.getElementById('ioncore-presale-popup')) return;

  const style = document.createElement('style');
  style.textContent = `
    #ioncore-presale-popup {
      position: fixed;
      right: clamp(12px, 2vw, 24px);
      bottom: clamp(12px, 2vw, 24px);
      z-index: 2147483000;
      width: min(360px, calc(100vw - 24px));
      color: #f7fff5;
      font-family: Montserrat, Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    #ioncore-presale-popup * { box-sizing: border-box; }
    .ioncore-presale-card {
      display: grid;
      gap: 12px;
      padding: 18px;
      border: 1px solid rgba(106, 255, 59, 0.48);
      border-radius: 22px;
      background: linear-gradient(145deg, rgba(4, 12, 22, 0.96), rgba(16, 42, 30, 0.94));
      box-shadow: 0 22px 70px rgba(0, 0, 0, 0.45), 0 0 46px rgba(106, 255, 59, 0.26);
      backdrop-filter: blur(16px);
    }
    .ioncore-presale-kicker {
      color: #6aff3b;
      font-size: 0.72rem;
      font-weight: 800;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }
    .ioncore-presale-title {
      margin: 0;
      color: #ffffff;
      font-size: 1.05rem;
      line-height: 1.25;
      font-weight: 900;
    }
    .ioncore-presale-copy {
      margin: 0;
      color: rgba(235, 246, 255, 0.84);
      font-size: 0.86rem;
      line-height: 1.5;
    }
    .ioncore-presale-actions { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .ioncore-presale-link {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 11px 16px;
      border-radius: 999px;
      background: linear-gradient(135deg, #6aff3b, #36d66a);
      color: #041016 !important;
      font-size: 0.86rem;
      font-weight: 900;
      text-decoration: none;
      box-shadow: 0 12px 34px rgba(106, 255, 59, 0.35);
    }
    .ioncore-presale-toggle {
      border: 1px solid rgba(255, 255, 255, 0.18);
      border-radius: 999px;
      padding: 9px 12px;
      background: rgba(255, 255, 255, 0.08);
      color: #ffffff;
      cursor: pointer;
      font: inherit;
      font-size: 0.8rem;
      font-weight: 800;
    }
    #ioncore-presale-popup.is-collapsed { width: auto; }
    #ioncore-presale-popup.is-collapsed .ioncore-presale-card { display: none; }
    #ioncore-presale-popup:not(.is-collapsed) .ioncore-presale-tab { display: none; }
    .ioncore-presale-tab {
      border: 1px solid rgba(106, 255, 59, 0.58);
      border-radius: 999px;
      padding: 12px 16px;
      background: linear-gradient(135deg, rgba(4, 12, 22, 0.96), rgba(14, 48, 28, 0.96));
      color: #ffffff;
      box-shadow: 0 14px 44px rgba(0, 0, 0, 0.38), 0 0 34px rgba(106, 255, 59, 0.24);
      cursor: pointer;
      font: inherit;
      font-size: 0.84rem;
      font-weight: 900;
    }
  `;

  const popup = document.createElement('aside');
  popup.id = 'ioncore-presale-popup';
  popup.setAttribute('aria-label', 'Unified Fundraising and Presale Launch');
  popup.innerHTML = `
    <div class="ioncore-presale-card">
      <div class="ioncore-presale-kicker">Highlighted launch</div>
      <h2 class="ioncore-presale-title">Unified Fundraising &amp; Presale Launch</h2>
      <p class="ioncore-presale-copy">Open the investment, presale, and launch overview from any page.</p>
      <div class="ioncore-presale-actions">
        <a class="ioncore-presale-link" href="/unified-fundraising-presale.html">Open launch page</a>
        <button class="ioncore-presale-toggle" type="button" aria-expanded="true">Collapse</button>
      </div>
    </div>
    <button class="ioncore-presale-tab" type="button" aria-expanded="false">Unified Fundraising &amp; Presale</button>
  `;

  const setCollapsed = (collapsed) => {
    popup.classList.toggle('is-collapsed', collapsed);
    popup.querySelectorAll('button[aria-expanded]').forEach((button) => {
      button.setAttribute('aria-expanded', String(!collapsed));
    });
  };

  popup.querySelector('.ioncore-presale-toggle').addEventListener('click', () => setCollapsed(true));
  popup.querySelector('.ioncore-presale-tab').addEventListener('click', () => setCollapsed(false));

  document.head.appendChild(style);
  document.body.appendChild(popup);
})();
