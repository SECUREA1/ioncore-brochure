(() => {
  const BUTTON_ID = "omconsole-launcher-button";
  const existing = document.getElementById(BUTTON_ID);
  if (existing) return;

  const targetUrl = new URL("omconsole_render_single_games_ROUTING.html", window.location.href).toString();

  const style = document.createElement("style");
  style.textContent = `
    #${BUTTON_ID} {
      position: fixed;
      top: 12px;
      left: 12px;
      z-index: 99999;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 14px;
      border-radius: 999px;
      border: 1px solid rgba(212, 175, 55, 0.35);
      background: linear-gradient(180deg, rgba(11, 42, 102, 0.95), rgba(5, 16, 32, 0.92));
      color: #f8fbff;
      font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
      font-weight: 800;
      letter-spacing: 0.18px;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.38), 0 0 0 1px rgba(255, 255, 255, 0.05) inset;
      cursor: pointer;
      transition: transform 0.16s cubic-bezier(.22, .61, .36, 1), filter 0.16s cubic-bezier(.22, .61, .36, 1);
    }
    #${BUTTON_ID}:hover { transform: translateY(-1px); filter: brightness(1.06); }
    #${BUTTON_ID}:active { transform: translateY(0px) scale(.99); }
    #${BUTTON_ID} .dot {
      width: 12px;
      height: 12px;
      border-radius: 999px;
      background: radial-gradient(circle at 30% 30%, #fefefe, #d4af37 65%, #0b2a66 100%);
      box-shadow: 0 0 0 4px rgba(212, 175, 55, 0.18), 0 0 26px rgba(212, 175, 55, 0.25);
      flex: none;
    }
  `;
  document.head.appendChild(style);

  const btn = document.createElement("button");
  btn.id = BUTTON_ID;
  btn.type = "button";
  btn.setAttribute("aria-label", "Open OMConsole");
  btn.innerHTML = `<span class="dot" aria-hidden="true"></span><span>Open OMConsole</span>`;

  btn.addEventListener("click", () => {
    const win = window.open(targetUrl, "_blank", "noopener,noreferrer");
    if (!win) {
      alert("Please allow popups to open the OMConsole in a new tab.");
    } else {
      win.focus();
    }
  });

  const ready = () => {
    if (!document.body.contains(btn)) {
      document.body.appendChild(btn);
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ready, { once: true });
  } else {
    ready();
  }
})();
