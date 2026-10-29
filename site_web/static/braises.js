// Braises dorées qui montent dans le héros de l'accueil. Coupées si l'utilisateur préfère moins d'animations.
(function () {
  const toile = document.getElementById("braises");
  if (!toile) return;
  const ctx = toile.getContext("2d");
  const calme = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let L = 0, H = 0, braises = [];
  function taille() {
    const r = toile.getBoundingClientRect(), d = Math.min(window.devicePixelRatio || 1, 2);
    L = r.width; H = r.height;
    toile.width = Math.round(L * d); toile.height = Math.round(H * d);
    ctx.setTransform(d, 0, 0, d, 0, 0);
    const n = Math.round(Math.min(90, L / 14));
    braises = Array.from({ length: n }, () => nouvelle(true));
  }
  function nouvelle(partout) {
    return { x: Math.random() * L, y: partout ? Math.random() * H : H + 10, r: 0.6 + Math.random() * 1.9,
      v: 0.25 + Math.random() * 0.9, d: (Math.random() - 0.5) * 0.4, vie: 0.4 + Math.random() * 0.6, t: Math.random() * 6.28 };
  }
  function dessiner() {
    ctx.clearRect(0, 0, L, H);
    for (const b of braises) {
      b.y -= b.v; b.t += 0.03; b.x += b.d + Math.sin(b.t) * 0.3;
      if (b.y < -10) Object.assign(b, nouvelle(false));
      const a = b.vie * Math.min(1, b.y / (H * 0.35));
      const g = ctx.createRadialGradient(b.x, b.y, 0, b.x, b.y, b.r * 4);
      g.addColorStop(0, `rgba(255,214,140,${a})`);
      g.addColorStop(0.4, `rgba(240,150,50,${a * 0.5})`);
      g.addColorStop(1, "rgba(240,120,30,0)");
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(b.x, b.y, b.r * 4, 0, 6.283); ctx.fill();
    }
    if (!calme) requestAnimationFrame(dessiner);
  }
  window.addEventListener("resize", taille);
  taille(); dessiner();
})();
