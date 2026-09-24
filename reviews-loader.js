(() => {
  const FUNPAY_URL = "https://funpay.com/users/624432/";

  const css = `
    .funpay-review-summary{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:0 0 22px;padding:18px 20px;background:linear-gradient(145deg,#111b26,#0c131c);border:1px solid var(--line);border-radius:12px}
    .funpay-review-score{display:flex;align-items:center;gap:16px}
    .funpay-review-score strong{font-size:40px;line-height:1;color:#fff}
    .funpay-review-score span{display:block;color:#ffd500;letter-spacing:2px;font-size:18px}
    .funpay-review-score small{display:block;color:var(--muted);font-size:11px;margin-top:3px}
    .funpay-review-summary .btn{white-space:nowrap}
    .reviews.funpay-live-reviews{grid-template-columns:repeat(3,1fr)}
    .review.funpay-live{display:flex;flex-direction:column;gap:9px;min-height:160px}
    .review.funpay-live .review-top b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:65%}
    .review.funpay-live .review-meta{color:#7e8da0;font-size:11px}
    .review.funpay-live .review-order{color:#aebdce;font-size:12px}
    .review.funpay-live .review-text{color:#e8edf3;font-size:14px;margin:4px 0 0}
    .funpay-review-status{grid-column:1/-1;color:var(--muted);font-size:13px}
    @media(max-width:900px){.reviews.funpay-live-reviews{grid-template-columns:repeat(2,1fr)}}
    @media(max-width:560px){.funpay-review-summary{align-items:flex-start;flex-direction:column}.reviews.funpay-live-reviews{grid-template-columns:1fr}}
  `;
  const style = document.createElement("style");
  style.textContent = css;
  document.head.appendChild(style);

  const esc = (s) => String(s ?? "").replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
  const stars = n => "★".repeat(Math.max(1, Math.min(5, Number(n) || 5)));

  function render(data){
    const section = document.querySelector("#reviews");
    const grid = section?.querySelector(".reviews");
    if(!section || !grid) return;

    const headingText = section.querySelector(".section-heading p:not(.eyebrow)");
    if(headingText) headingText.textContent = "Свежие отзывы автоматически загружаются из профиля FunPay.";

    const oldSummary = section.querySelector(".funpay-review-summary");
    if(oldSummary) oldSummary.remove();

    const rating = Number(data.rating || 5).toFixed(1).replace(".0", "");
    const countText = data.total_reviews ? `${Number(data.total_reviews).toLocaleString("ru-RU")} отзывов` : "Отзывы FunPay";
    const summary = document.createElement("div");
    summary.className = "funpay-review-summary";
    summary.innerHTML = `
      <div class="funpay-review-score">
        <strong>${esc(rating)}</strong>
        <div><span>${stars(Math.round(Number(data.rating || 5)))}</span><small>${esc(countText)} · FunPay</small></div>
      </div>
      <a class="btn btn-primary" href="${FUNPAY_URL}" target="_blank" rel="noopener">Все отзывы на FunPay →</a>`;
    grid.before(summary);

    grid.classList.add("funpay-live-reviews");
    const reviews = Array.isArray(data.reviews) ? data.reviews.slice(0, 9) : [];
    if(!reviews.length){
      grid.innerHTML = `<p class="funpay-review-status">Пока не удалось загрузить отзывы. <a href="${FUNPAY_URL}" target="_blank" rel="noopener">Открыть FunPay</a></p>`;
      return;
    }

    grid.innerHTML = reviews.map(r => `
      <article class="review funpay-live">
        <div class="review-top"><b>${esc(r.author || "Покупатель")}</b><span>${stars(r.stars)}</span></div>
        <div class="review-order">Заказ #${esc(r.order_id || "")}${r.price ? ` · ${esc(r.price)}` : ""}</div>
        ${r.date ? `<div class="review-meta">${esc(r.date)}</div>` : ""}
        <p class="review-text">${esc(r.text || "Отзыв без текста")}</p>
      </article>`).join("");
  }

  fetch(`reviews.json?v=${Date.now()}`, {cache:"no-store"})
    .then(r => { if(!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
    .then(render)
    .catch(err => {
      console.warn("FunPay reviews load failed:", err);
      const grid = document.querySelector("#reviews .reviews");
      if(grid){
        grid.innerHTML = `<p class="funpay-review-status">Отзывы доступны в профиле FunPay. <a href="${FUNPAY_URL}" target="_blank" rel="noopener">Посмотреть все отзывы →</a></p>`;
      }
    });
})();
