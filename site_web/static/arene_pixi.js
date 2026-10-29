/* 2Hot4Deck · l'arène animée de la tour (PixiJS, dessinée sur la carte graphique).
   Le combat est toujours calculé par le moteur du jeu ; ce fichier ne fait que le rejouer en animation.
   Si l'ordinateur ne gère pas WebGL, le site garde l'ancienne arène. */
(function () {
  "use strict";
  if (!window.PIXI) return;
  const P = PIXI;
  const calme = () => window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  let app = null, dlg = null, hote = null, vitesse = 1, jeton = 0, options = {};
  let monde, fond, ambiance, voile, derriere, unitesC, fx, hud;
  let L = 800, H = 600, couv = { s: 1, x: 0, y: 0, w: 1, h: 1 };
  let unites = [], tex = {}, combat = null, banniere = null;
  const parts = [];
  const hasard = (a, b) => a + Math.random() * (b - a);
  const nb = (n) => Math.round(n).toLocaleString("fr-FR");
  const court = (n) => (n >= 10000 ? (n / 1000).toFixed(n >= 100000 ? 0 : 1).replace(".", ",") + " k" : nb(n));
  const ease = { out: (t) => 1 - (1 - t) ** 3, inout: (t) => (t < .5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2), back: (t) => 1 + 2.7 * (t - 1) ** 3 + 1.7 * (t - 1) ** 2 };
  const attendre = (ms) => new Promise((r) => { let t = 0; const f = () => { t += app.ticker.deltaMS * vitesse; if (t >= ms) { app.ticker.remove(f); r(); } }; app.ticker.add(f); });
  function tween(obj, vers, ms, e = ease.out) {
    const de = {}; for (const k in vers) de[k] = k.split(".").reduce((o, p) => o[p], obj);
    const ecrire = (k, v) => { const ch = k.split("."); const der = ch.pop(); const o = ch.reduce((o, p) => o && o[p], obj); if (o && !o.destroyed) o[der] = v; };
    return new Promise((r) => { let t = 0; const f = () => { t += app.ticker.deltaMS * vitesse; const k = Math.min(1, t / ms), q = e(k);
      if (obj.destroyed) { app.ticker.remove(f); r(); return; }
      for (const c in vers) ecrire(c, de[c] + (vers[c] - de[c]) * q); if (k >= 1) { app.ticker.remove(f); r(); } }; app.ticker.add(f); });
  }

  // ---------------------------------------------------------------- textures fabriquées à la volée
  function canvas(w, h) { const c = document.createElement("canvas"); c.width = w; c.height = h; return [c, c.getContext("2d")]; }
  function texPoint() {
    const [c, x] = canvas(64, 64); const g = x.createRadialGradient(32, 32, 0, 32, 32, 32);
    g.addColorStop(0, "rgba(255,255,255,1)"); g.addColorStop(.35, "rgba(255,255,255,.55)"); g.addColorStop(1, "rgba(255,255,255,0)");
    x.fillStyle = g; x.fillRect(0, 0, 64, 64); return P.Texture.from(c);
  }
  function texRayons() {
    const [c, x] = canvas(512, 512); x.translate(256, 256);
    for (let i = 0; i < 16; i++) {
      x.save(); x.rotate((Math.PI * 2 / 16) * i + (i % 2) * .08); const larg = i % 2 ? 22 : 38;
      for (let p = 6; p >= 1; p--) {
        const g = x.createLinearGradient(0, 0, 0, -256); g.addColorStop(0, `rgba(255,255,255,${.1 + .12 * (7 - p)})`); g.addColorStop(.55, `rgba(255,255,255,${.06 * (7 - p)})`); g.addColorStop(1, "rgba(255,255,255,0)");
        x.fillStyle = g; const w = larg * p / 6; x.beginPath(); x.moveTo(-w * .12, 0); x.lineTo(-w, -256); x.lineTo(w, -256); x.lineTo(w * .12, 0); x.fill();
      }
      x.restore();
    }
    x.globalCompositeOperation = "destination-in";
    const m = x.createRadialGradient(0, 0, 0, 0, 0, 256); m.addColorStop(0, "rgba(0,0,0,1)"); m.addColorStop(.35, "rgba(0,0,0,.85)"); m.addColorStop(1, "rgba(0,0,0,0)");
    x.fillStyle = m; x.fillRect(-256, -256, 512, 512);
    x.globalCompositeOperation = "lighter";
    const coeur = x.createRadialGradient(0, 0, 0, 0, 0, 120); coeur.addColorStop(0, "rgba(255,255,255,.55)"); coeur.addColorStop(1, "rgba(255,255,255,0)"); x.fillStyle = coeur; x.fillRect(-256, -256, 512, 512);
    return P.Texture.from(c);
  }
  function texPlasma() {
    const [c, x] = canvas(1024, 256);
    const g = x.createLinearGradient(0, 0, 0, 256); g.addColorStop(0, "rgba(255,255,255,0)"); g.addColorStop(.3, "rgba(255,255,255,.35)"); g.addColorStop(.5, "rgba(255,255,255,1)"); g.addColorStop(.7, "rgba(255,255,255,.35)"); g.addColorStop(1, "rgba(255,255,255,0)");
    x.fillStyle = g; x.fillRect(0, 0, 1024, 256);
    for (let i = 0; i < 70; i++) { const y = 128 + (Math.random() - .5) * 170, l = 80 + Math.random() * 380, x0 = Math.random() * 1024, e = 2 + Math.random() * 10, a = .08 + Math.random() * .25;
      const f = x.createLinearGradient(x0, 0, x0 + l, 0); f.addColorStop(0, "rgba(255,255,255,0)"); f.addColorStop(.5, `rgba(255,255,255,${a})`); f.addColorStop(1, "rgba(255,255,255,0)");
      x.fillStyle = f; for (const dx of [0, -1024, 1024]) { x.beginPath(); x.ellipse(x0 + l / 2 + dx, y, l / 2, e, 0, 0, 6.283); x.fill(); } }
    return P.Texture.from(c);
  }
  function texBulle() {
    const [c, x] = canvas(256, 256); const g = x.createRadialGradient(128, 128, 0, 128, 128, 128);
    g.addColorStop(0, "rgba(255,255,255,.06)"); g.addColorStop(.62, "rgba(255,255,255,.12)"); g.addColorStop(.82, "rgba(255,255,255,.55)"); g.addColorStop(.9, "rgba(255,255,255,.9)"); g.addColorStop(.96, "rgba(255,255,255,.3)"); g.addColorStop(1, "rgba(255,255,255,0)");
    x.fillStyle = g; x.fillRect(0, 0, 256, 256);
    const h = x.createRadialGradient(92, 78, 0, 92, 78, 60); h.addColorStop(0, "rgba(255,255,255,.45)"); h.addColorStop(1, "rgba(255,255,255,0)"); x.fillStyle = h; x.fillRect(0, 0, 256, 256);
    return P.Texture.from(c);
  }
  function texReflet() {
    const [c, x] = canvas(256, 256); const g = x.createConicGradient ? x.createConicGradient(0, 128, 128) : null;
    if (g) { g.addColorStop(0, "rgba(255,255,255,0)"); g.addColorStop(.08, "rgba(255,255,255,.8)"); g.addColorStop(.2, "rgba(255,255,255,0)"); g.addColorStop(1, "rgba(255,255,255,0)"); x.strokeStyle = g; }
    else x.strokeStyle = "rgba(255,255,255,.5)";
    x.lineWidth = 10; x.beginPath(); x.arc(128, 128, 104, 0, g ? 6.283 : 1.2); x.stroke();
    return P.Texture.from(c);
  }
  let POINT, RAYONS, PLASMA, BULLE, REFLET;

  // ---------------------------------------------------------------- mise en place (une seule fois)
  function preparer() {
    if (app) return true;
    try { if (!P.utils.isWebGLSupported()) return false; } catch (e) { return false; }
    dlg = document.createElement("dialog");
    dlg.id = "arene3d"; dlg.className = "arene3d"; dlg.setAttribute("aria-label", "Combat de la tour");
    dlg.innerHTML = `<div class="a3-scene" aria-hidden="true"></div>
      <div class="a3-barre"><div class="ar-titre" id="a3-titre"></div>
        <div class="ar-vitesse" role="group" aria-label="Vitesse du combat">
          <button type="button" data-v3="1" aria-pressed="true">x1</button><button type="button" data-v3="2" aria-pressed="false">x2</button><button type="button" data-v3="4" aria-pressed="false">x4</button>
          <button type="button" data-v3="fin">Passer</button></div></div>
      <p class="a3-ligne" id="a3-ligne" aria-live="polite"></p>
      <div class="ar-fin" id="a3-fin" hidden></div>`;
    document.body.appendChild(dlg);
    hote = dlg.querySelector(".a3-scene");
    app = new P.Application({ resizeTo: hote, backgroundColor: 0x04060c, antialias: true, autoDensity: true, resolution: Math.min(devicePixelRatio || 1, 2) });
    hote.appendChild(app.view);
    POINT = texPoint(); RAYONS = texRayons(); PLASMA = texPlasma(); BULLE = texBulle(); REFLET = texReflet();
    monde = new P.Container(); app.stage.addChild(monde);
    fond = new P.Sprite(); monde.addChild(fond);
    ambiance = new P.Container(); monde.addChild(ambiance);
    voile = new P.Graphics(); monde.addChild(voile);
    derriere = new P.Container(); monde.addChild(derriere);
    unitesC = new P.Container(); unitesC.sortableChildren = true; monde.addChild(unitesC);
    fx = new P.Container(); monde.addChild(fx);
    hud = new P.Container(); app.stage.addChild(hud);
    app.ticker.add(bouclePart);
    app.ticker.add(boucleCamera);
    app.ticker.add(boucleAmbiance);
    app.ticker.add(boucleRespiration);
    app.renderer.on("resize", placer);
    dlg.addEventListener("click", (e) => {
      const v = e.target.closest("[data-v3]"); if (!v) return;
      if (v.dataset.v3 === "fin") { passer(); return; }
      vitesse = Number(v.dataset.v3); boutonsVitesse();
    });
    dlg.addEventListener("close", () => { jeton++; nettoyer(); app.stop(); });
    lueurs = braseros.map(() => { const s = new P.Sprite(POINT); s.anchor.set(.5); s.blendMode = P.BLEND_MODES.ADD; s.tint = 0xff8a30; ambiance.addChild(s); return s; });
    return true;
  }
  function boutonsVitesse() { dlg.querySelectorAll("[data-v3]").forEach((b) => b.setAttribute("aria-pressed", String(Number(b.dataset.v3) === vitesse))); }

  // ---------------------------------------------------------------- particules et petits effets
  function particule(o) {
    const s = new P.Sprite(POINT); s.anchor.set(.5); s.blendMode = P.BLEND_MODES.ADD; s.tint = o.couleur ?? 0xffc060;
    s.x = o.x; s.y = o.y; Object.assign(s, { vx: o.vx || 0, vy: o.vy || 0, vie: o.vie || 600, max: o.vie || 600, t0: o.taille || 10, t1: o.fin ?? (o.taille || 10) * .2,
      g: o.gravite || 0, a0: o.alpha ?? 1, frein: o.frein ?? 1 });
    s.width = s.height = s.t0; (o.calque || fx).addChild(s); parts.push(s); return s;
  }
  function bouclePart() {
    const dt = app.ticker.deltaMS * vitesse;
    for (let i = parts.length - 1; i >= 0; i--) {
      const p = parts[i]; if (p.destroyed) { parts.splice(i, 1); continue; }
      p.vie -= dt;
      if (p.vie <= 0) { p.destroy(); parts.splice(i, 1); continue; }
      p.vx *= p.frein ** (dt / 16); p.vy *= p.frein ** (dt / 16); p.vy += p.g * dt; p.x += p.vx * dt; p.y += p.vy * dt;
      const k = p.vie / p.max; p.alpha = p.a0 * Math.min(1, k * 2.5); const t = p.t1 + (p.t0 - p.t1) * k; p.width = p.height = t;
    }
  }
  function gerbe(x, y, n, couleur, force = .5, taille = 10, vie = 600, gravite = .0006) {
    for (let i = 0; i < n; i++) { const a = hasard(0, 6.283), v = hasard(.2, 1) * force;
      particule({ x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - force * .3, vie: hasard(vie * .6, vie), taille: hasard(taille * .5, taille), couleur, gravite, frein: .96 }); }
  }
  const flash = (x, y, taille, couleur, vie = 320) => particule({ x, y, taille, fin: taille * 1.6, vie, couleur, alpha: .9 });
  const halo = (x, y, taille, couleur, alpha, vie) => particule({ x, y, taille, fin: taille * 1.3, vie, couleur, alpha });
  function onde(x, y, rayon, couleur, ms = 520, epais = 6) {
    const g = new P.Graphics(); g.blendMode = P.BLEND_MODES.ADD; g.x = x; g.y = y; fx.addChild(g); let t = 0;
    const f = () => { if (g.destroyed) { app.ticker.remove(f); return; } t += app.ticker.deltaMS * vitesse; const k = Math.min(1, t / ms); g.clear(); g.lineStyle(epais * (1 - k * .6), couleur, 1 - k);
      g.drawEllipse(0, 0, rayon * (.15 + .85 * ease.out(k)), rayon * .5 * (.15 + .85 * ease.out(k))); if (k >= 1) { app.ticker.remove(f); g.destroy(); } };
    app.ticker.add(f);
  }
  let secousseForce = 0;
  const secousse = (f) => { secousseForce = Math.max(secousseForce, calme() ? 0 : f); };
  function boucleCamera() { secousseForce *= .88 ** (app.ticker.deltaMS / 16); monde.x = (Math.random() - .5) * secousseForce * 2; monde.y = (Math.random() - .5) * secousseForce * 2; }
  const braseros = [[.035, .57], [.965, .57], [.16, .74], [.84, .74], [.29, .79], [.71, .79]];
  let lueurs = [];
  function boucleAmbiance() {
    const t = performance.now() / 1000;
    lueurs.forEach((s, i) => { const [a, b] = braseros[i]; s.x = couv.x + a * couv.w; s.y = couv.y + b * couv.h; s.width = s.height = couv.w * .09 * (1 + .12 * Math.sin(t * 7 + i * 2) + .06 * Math.sin(t * 13 + i)); s.alpha = .45 + .1 * Math.sin(t * 9 + i); });
    if (!calme() && Math.random() < .5 * vitesse) { const [a, b] = braseros[(Math.random() * braseros.length) | 0];
      particule({ x: couv.x + a * couv.w + hasard(-20, 20), y: couv.y + b * couv.h, vx: hasard(-.02, .02), vy: hasard(-.09, -.04), vie: hasard(1800, 3600), taille: hasard(3, 7), fin: 1, couleur: 0xffa040, calque: ambiance }); }
  }
  function boucleRespiration() {
    const t = performance.now() / 1000;
    unites.forEach((c, i) => { if (c.ko || c.destroyed) return; const r = c.u.boss ? .012 : .02; c.corps.scale.set(1 + Math.sin(t * 1.6 + i) * r * .5); c.corps.y = Math.sin(t * 1.3 + i * 1.7) * (c.u.boss ? 3 : 4); c.aura.alpha = .25 + .1 * Math.sin(t * 2 + i); });
  }
  function nettoyer() {
    unites.forEach((c) => { if (!c.destroyed) c.destroy({ children: true }); }); unites = [];
    for (const cont of [fx, hud, derriere]) cont.removeChildren().forEach((o) => o.destroy({ children: true }));
    parts.length = 0; voile.alpha = 0; banniere = null;
  }

  // ---------------------------------------------------------------- les cartes
  const RAR = { N: 0x8f9bb3, R: 0x4f9be8, SR: 0xa66bf0, SSR: 0xf0a23a, UR: 0xf0506e, LR: 0xff3b3b };
  const styleTexte = (taille, couleur = 0xece4cf) => new P.TextStyle({ fontFamily: "Barlow, Segoe UI, sans-serif", fontWeight: "700", fontSize: taille, fill: couleur, dropShadow: true, dropShadowColor: 0x000000, dropShadowBlur: 4, dropShadowDistance: 1 });
  function texDe(url) { return (url && tex[url]) || P.Texture.WHITE; }
  function creerUnite(u, k) {
    const c = new P.Container(); c.u = u; c.k = k; c.pv = u.pv; c.bouclier = u.bouclier || 0;
    const aura = new P.Sprite(POINT); aura.anchor.set(.5); aura.blendMode = P.BLEND_MODES.ADD; aura.tint = u.boss ? 0xff3b2b : (RAR[u.rarete] || 0xffffff); aura.alpha = .35; c.addChild(aura); c.aura = aura;
    const corps = new P.Container(); c.addChild(corps); c.corps = corps;
    const img = new P.Sprite(texDe(u.image)); img.anchor.set(.5); corps.addChild(img); c.img = img;
    if (!u.image || !tex[u.image]) { img.tint = 0x1a2233; c.nomVide = new P.Text(u.nom, styleTexte(16)); c.nomVide.anchor.set(.5); corps.addChild(c.nomVide); }
    if (u.boss) {
      const masque = new P.Graphics(); corps.addChild(masque); img.mask = masque; c.masque = masque;
      const cadre = new P.Sprite(texDe(options.cadreBoss)); cadre.anchor.set(.5); corps.addChild(cadre); c.cadre = cadre;
      const barre = new P.Container(); c.addChild(barre); c.barre = barre;
      c.jauge = new P.Graphics(); barre.addChild(c.jauge);
      c.barreCadre = new P.Sprite(texDe(options.barreBoss)); c.barreCadre.anchor.set(.5, 0); barre.addChild(c.barreCadre);
      c.texte = new P.Text("", styleTexte(13)); c.texte.anchor.set(.5); barre.addChild(c.texte);
      c.nom = new P.Text(u.nom.replace(" adverse", "").toUpperCase(), new P.TextStyle({ fontFamily: "Cinzel, Georgia, serif", fontWeight: "700", fontSize: 18, fill: 0xece4cf, letterSpacing: 4, dropShadow: true, dropShadowBlur: 6, dropShadowDistance: 0 }));
      c.nom.anchor.set(.5); c.addChild(c.nom);
    } else {
      c.jauge = new P.Graphics(); c.addChild(c.jauge);
      c.texte = new P.Text("", styleTexte(11)); c.texte.anchor.set(.5); c.addChild(c.texte);
      c.icones = (options.icones ? options.icones(u) : []).filter((url) => tex[url]).map((url) => {   // l'item et la rune portés
        const s = new P.Sprite(tex[url]); s.anchor.set(.5); corps.addChild(s); return s; });
      c.pips = new P.Graphics(); c.addChild(c.pips);
    }
    unitesC.addChild(c); return c;
  }
  function placer() {
    if (!app) return;
    L = app.screen.width; H = app.screen.height;
    const t = fond.texture; if (t && t.width > 1) { const s = Math.max(L / t.width, H / t.height); fond.scale.set(s); fond.x = (L - t.width * s) / 2; fond.y = (H - t.height * s) * .62;
      couv = { s, x: fond.x, y: fond.y, w: t.width * s, h: t.height * s }; }
    if (!unites.length) return;
    const eux = unites.filter((c) => c.u.camp === 1), nous = unites.filter((c) => c.u.camp === 0);
    const barre = dlg.querySelector(".a3-barre"), ligne = dlg.querySelector(".a3-ligne");
    const haut = barre.offsetHeight + 8, dispo = H - haut - (ligne.offsetHeight || 0) - 14;
    const boss = eux.length === 1 && eux[0].u.boss ? eux[0] : null;
    const nMax = Math.max(nous.length, boss ? 1 : eux.length, 3);
    const hNous = (k) => Math.min(k * nMax * 1.14 * .59 > L * .94 ? L * .94 / nMax / 1.14 / .59 : k, 280);
    let hc = hNous(dispo * .38), wc = hc * .59;
    let wb = boss ? Math.min(L * .94, 900) : 0, hb = wb / 2.5;
    const hautBoss = () => hb * 1.32 + 30;
    const hautEux = () => (boss ? hautBoss() : hc * .92 + 30);
    const total = () => hautEux() + hc + 40;
    if (total() > dispo * .96) {
      const part = dispo * .96;
      if (boss) { hb = Math.min(hb, (part * .5 - 30) / 1.32); wb = hb * 2.5; }
      hc = Math.min(hc, part - hautEux() - 40); wc = hc * .59;
    }
    const vide = Math.max(0, dispo - total()), pas = Math.min(vide / 3, 40), marge = (vide - pas) / 2;
    const yHaut = haut + marge, yNous = yHaut + hautEux() + pas;
    nous.forEach((c, i) => { const n = nous.length; c.base = { x: L / 2 + (i - (n - 1) / 2) * (wc * 1.14), y: yNous + hc / 2 }; dimensionCarte(c, wc, hc); });
    if (boss) {
      const c = boss, w = wb, h = hb; c.base = { x: L / 2, y: yHaut + h / 2 };
      c.cadre.width = w; c.cadre.height = h;
      const iw = w * .876, ih = h * .696; const s = Math.max(iw / c.img.texture.width, ih / c.img.texture.height); c.img.scale.set(s);
      c.masque.clear(); c.masque.beginFill(0xffffff); c.masque.drawRect(-iw / 2, -ih / 2, iw, ih); c.masque.endFill();
      c.aura.width = w * 1.3; c.aura.height = h * 1.8;
      c.nom.style.fontSize = Math.max(11, Math.min(20, w * .028)); c.nom.y = h / 2 + c.nom.height * .55;
      const bw = Math.min(w * .78, 640), bh = bw * 290 / 2171; c.barre.y = c.nom.y + c.nom.height * .5; c.barreCadre.width = bw; c.barreCadre.height = bh;
      c.bar = { x: -bw / 2 + bw * .0925, y: bh * .475, w: bw * (1 - .0925 - .096), h: bh * .267 }; c.texte.style.fontSize = Math.max(9, bh * .2); c.texte.y = c.bar.y + c.bar.h / 2;
      c.dims = { w, h };
    } else eux.forEach((c, i) => { const n = eux.length; c.base = { x: L / 2 + (i - (n - 1) / 2) * (wc * 1.1), y: yHaut + hc * .46 }; dimensionCarte(c, wc * .92, hc * .92); });
    unites.forEach((c) => { if (!c.enMouvement) { c.x = c.base.x; c.y = c.base.y; } dessinerPv(c); });
  }
  function dimensionCarte(c, w, h) {
    const tw = c.img.texture.width || 1, th = c.img.texture.height || 1;
    if (c.nomVide) { c.img.width = w; c.img.height = h; c.nomVide.style.fontSize = Math.max(10, w * .1); c.nomVide.style.wordWrap = true; c.nomVide.style.wordWrapWidth = w * .9; c.nomVide.style.align = "center"; }
    else { const s = Math.min(w / tw, h / th); c.img.scale.set(s); }
    c.aura.width = w * 1.9; c.aura.height = h * 1.5;
    c.bar = { x: -w * .48, y: h / 2 + 8, w: w * .96, h: Math.max(10, h * .05) }; c.texte.style.fontSize = Math.max(9, c.bar.h * .8); c.texte.y = c.bar.y + c.bar.h / 2;
    (c.icones || []).forEach((s, i) => { const z = w * .2; s.width = s.height = z; s.x = -w / 2 + z * .7 + i * z * 1.08; s.y = h / 2 - z * .75; });
    c.dims = { w, h };
  }
  function dessinerPv(c) {
    if (c.destroyed) return;
    const g = c.jauge, b = c.bar, k = Math.max(0, Math.min(1, c.pv / c.u.pvmax)), kb = Math.min(1, c.bouclier / c.u.pvmax); g.clear();
    if (!c.u.boss) { g.beginFill(0x000000, .7); g.lineStyle(1, 0xd9b25f, .6); g.drawRoundedRect(b.x, b.y, b.w, b.h, b.h / 3); g.endFill(); g.lineStyle(0); }
    else { g.beginFill(0x0a0607); g.drawRoundedRect(b.x, b.y, b.w, b.h, b.h / 2); g.endFill(); }
    if (k > 0) { g.beginFill(c.u.camp === 0 ? 0x2fbf66 : 0xe3121c); g.drawRoundedRect(b.x, b.y, b.w * k, b.h, b.h / 2); g.endFill();
      g.beginFill(0xffffff, .22); g.drawRoundedRect(b.x, b.y, b.w * k, b.h * .45, b.h / 3); g.endFill(); }
    if (kb > 0) { g.beginFill(0xcfe6ff, .75); g.drawRect(b.x, b.y, b.w * kb, b.h * .35); g.endFill(); }
    c.texte.text = `${court(Math.max(0, c.pv))} / ${court(c.u.pvmax)}`;
    if (c.pips && c.u.cout) {   // la jauge d'ulti : des losanges qui se remplissent
      const p = c.pips; p.clear(); const n = c.u.cout, z = Math.min(9, b.w / n / 2.2), y = b.y + b.h + z + 4;
      for (let i = 0; i < n; i++) { const x = (i - (n - 1) / 2) * z * 2.3; p.beginFill(i < Math.min(c.jaugeV ?? 0, n) ? 0xf0c46a : 0x000000, i < (c.jaugeV ?? 0) ? 1 : .55);
        p.lineStyle(1, 0xd9b25f, .8); p.drawPolygon([x, y - z, x + z * .7, y, x, y + z, x - z * .7, y]); p.endFill(); }
    }
  }

  // ---------------------------------------------------------------- chiffres, coups, K.O.
  function nombre(c, valeur, soin) {
    const t = new P.Text((soin ? "+" : "-") + nb(Math.abs(valeur)), new P.TextStyle({ fontFamily: "Cinzel, Georgia, serif", fontWeight: "900", fontSize: Math.max(22, (c.dims?.h || 200) * (c.u.boss ? .2 : .13)),
      fill: soin ? [0xc8ffd8, 0x3ddc84] : [0xfff4d6, 0xffb040, 0xe0301c], fillGradientStops: soin ? [0, 1] : [0, .5, 1], stroke: 0x1a0505, strokeThickness: 5, dropShadow: true, dropShadowBlur: 8, dropShadowDistance: 0, dropShadowColor: soin ? 0x00ff88 : 0xff5a00 }));
    t.anchor.set(.5); t.x = c.x + hasard(-20, 20); t.y = c.y - (c.dims?.h || 200) * .15; t.scale.set(.3); hud.addChild(t);
    tween(t.scale, { x: 1.15, y: 1.15 }, 160, ease.back).then(() => tween(t.scale, { x: 1, y: 1 }, 120));
    tween(t, { y: t.y - 70, alpha: 0 }, 1300, (k) => k * k).then(() => t.destroy());
  }
  function toucher(c, apres, sansAnim) {
    if (c.destroyed || (c.fige && !sansAnim)) return;
    const [pv, bouclier, jauge] = apres, d = pv - c.pv; c.bouclier = bouclier; if (jauge !== undefined) c.jaugeV = jauge;
    if (sansAnim) { c.pv = pv; dessinerPv(c); if (pv <= 0 && !c.ko) { c.ko = true; c.corps.alpha = .18; c.img.tint = 0x666666; c.aura.visible = false; } return; }
    if (d !== 0) { nombre(c, d, d > 0);
      if (d < 0) { c.img.tint = 0xff7070; setTimeout(() => { if (!c.destroyed && !c.ko) c.img.tint = c.nomVide ? 0x1a2233 : 0xffffff; }, 140 / vitesse); gerbe(c.x, c.y, 10, 0xffb070, .45, 10, 500); }
      else gerbe(c.x, c.y + (c.dims?.h || 100) * .3, 14, 0x60ff9a, .25, 9, 900, -.0002); }
    const anim = { v: c.pv }; c.pv = pv;
    const f = () => { if (c.destroyed) { app.ticker.remove(f); return; } c.pv = anim.v; dessinerPv(c); if (anim.v === pv) app.ticker.remove(f); };
    app.ticker.add(f); tween(anim, { v: pv }, 380);
    if (pv <= 0 && !c.ko) briser(c);
  }
  function briser(c) {
    c.ko = true; secousse(10); flash(c.x, c.y, (c.dims?.w || 200) * 1.4, 0xffffff, 300);
    const tx = c.img.texture;
    if (tx !== P.Texture.WHITE) {
      const bt = tx.baseTexture, cols = c.u.boss ? 8 : 4, lig = c.u.boss ? 4 : 6, fw = tx.frame.width / cols, fh = tx.frame.height / lig;
      const sx = c.img.scale.x, larg = tx.frame.width * sx, haut = tx.frame.height * sx;
      for (let i = 0; i < cols; i++) for (let j = 0; j < lig; j++) {
        const s = new P.Sprite(new P.Texture(bt, new P.Rectangle(tx.frame.x + i * fw, tx.frame.y + j * fh, fw, fh))); s.anchor.set(.5); s.scale.set(sx);
        s.x = c.x - larg / 2 + (i + .5) * fw * sx; s.y = c.y - haut / 2 + (j + .5) * fh * sx; fx.addChild(s);
        const vx = (s.x - c.x) * hasard(.004, .01), vr = hasard(-.012, .012); let t = 0, vyy = hasard(-.5, -.15);
        const f = () => { if (s.destroyed) { app.ticker.remove(f); return; } const dt = app.ticker.deltaMS * vitesse; t += dt; vyy += .0016 * dt; s.x += vx * dt; s.y += vyy * dt; s.rotation += vr * dt; s.alpha = Math.max(0, 1 - t / 1100);
          if (t > 1100) { app.ticker.remove(f); s.destroy(); } };
        app.ticker.add(f);
      }
    }
    gerbe(c.x, c.y, 40, 0xffd28a, .7, 12, 900);
    c.corps.alpha = .18; c.img.tint = 0x666666; c.aura.visible = false;
  }

  // ---------------------------------------------------------------- mise en scène commune
  async function annoncer(nom, camp) {
    voile.clear(); voile.beginFill(0x000000); voile.drawRect(-50, -50, L + 100, H + 100); voile.endFill(); voile.alpha = 0; tween(voile, { alpha: .55 }, 220);
    if (banniere && !banniere.destroyed) banniere.destroy();
    banniere = new P.Text(nom, new P.TextStyle({ fontFamily: "Cinzel, Georgia, serif", fontWeight: "900", fontSize: Math.min(64, L * .08), letterSpacing: 2,
      fill: camp === 0 ? [0xfff2c4, 0xf0c46a, 0xa7772d] : [0xffd0c8, 0xff5a5a, 0x8e0710], fillGradientStops: [0, .5, 1], stroke: 0x140a02, strokeThickness: 6,
      dropShadow: true, dropShadowBlur: 18, dropShadowDistance: 0, dropShadowColor: camp === 0 ? 0xf0a030 : 0xff2020, wordWrap: true, wordWrapWidth: L * .9, align: "center" }));
    banniere.anchor.set(.5); banniere.x = L / 2; banniere.y = H * .5; banniere.alpha = 0; banniere.scale.set(1.6);
    const bande = new P.Graphics(); const hb = banniere.height * 1.5;
    for (let i = 0; i < 24; i++) { const k = Math.sin((i / 23) * Math.PI); bande.beginFill(camp === 0 ? 0x0a0702 : 0x1a0306, .85 * k); bande.drawRect(i * L / 24, -hb / 2, L / 24 + 1, hb); bande.endFill(); }
    const bloc = new P.Container(); bloc.addChild(bande); hud.addChild(bloc); bloc.y = banniere.y; banniere.bande = bloc; bande.alpha = 0; tween(bande, { alpha: 1 }, 180);
    hud.addChild(banniere);
    tween(banniere, { alpha: 1 }, 180); await tween(banniere.scale, { x: 1, y: 1 }, 260, ease.back);
  }
  function finAnnonce() {
    tween(voile, { alpha: 0 }, 300);
    if (banniere && !banniere.destroyed) { const b = banniere; banniere = null; const bd = b.bande;
      tween(bd, { alpha: 0 }, 300).then(() => { if (!bd.destroyed) bd.destroy({ children: true }); }); tween(b, { alpha: 0, y: b.y - 30 }, 300).then(() => { if (!b.destroyed) b.destroy(); }); }
  }
  async function mettreEnAvant(c) {
    const r = new P.Sprite(RAYONS); r.anchor.set(.5); r.blendMode = P.BLEND_MODES.ADD; r.tint = c.u.camp === 0 ? 0xffcf70 : 0xff4a3a; r.x = c.x; r.y = c.y;
    r.width = r.height = (c.dims?.h || 300) * 2.2; r.alpha = 0; derriere.addChild(r);
    const tour = () => { if (r.destroyed) { app.ticker.remove(tour); return; } r.rotation += .0012 * app.ticker.deltaMS * vitesse; }; app.ticker.add(tour);
    tween(r, { alpha: .8 }, 250); c.zIndex = 5;
    await tween(c.scale, { x: 1.12, y: 1.12 }, 260, ease.back);
    return async () => { app.ticker.remove(tour); tween(c.scale, { x: 1, y: 1 }, 260); await tween(r, { alpha: 0 }, 300); if (!r.destroyed) r.destroy(); c.zIndex = 0; };
  }
  const cibles = (c, avant, apres) => unites.filter((x) => x.u.camp !== c.u.camp && apres[x.k][0] < avant[x.k][0]);
  const vivantsEnFace = (c, avant) => unites.filter((x) => x.u.camp !== c.u.camp && avant[x.k][0] > 0);

  async function attaqueSimple(c, avant, apres) {
    const vs = cibles(c, avant, apres); const t = vs[0];
    if (!t) { apres.forEach((e, k) => toucher(unites[k], e)); return; }
    const dx = (t.x - c.x) * .28, dy = (t.y - c.y) * .28; c.enMouvement = true;
    await tween(c, { x: c.base.x + dx, y: c.base.y + dy }, 170, ease.inout);
    for (const v of vs) entaille(v, c.u.camp === 0 ? 0xffe2a0 : 0xff6a50);
    apres.forEach((e, k) => toucher(unites[k], e)); secousse(4);
    await tween(c, { x: c.base.x, y: c.base.y }, 220, ease.out); c.enMouvement = false;
  }
  function entaille(v, couleur) {
    const g = new P.Graphics(); g.blendMode = P.BLEND_MODES.ADD; g.x = v.x; g.y = v.y; g.rotation = hasard(-.9, -.4); fx.addChild(g); const R = (v.dims?.h || 200) * .35; let t = 0;
    const f = () => { if (g.destroyed) { app.ticker.remove(f); return; } t += app.ticker.deltaMS * vitesse; const k = Math.min(1, t / 260); g.clear(); g.lineStyle(10 * (1 - k), couleur, 1 - k); g.arc(0, 0, R, -1.2, -1.2 + 2.4 * ease.out(Math.min(1, k * 2)));
      g.lineStyle(3 * (1 - k), 0xffffff, 1 - k); g.arc(0, 0, R, -1.2, -1.2 + 2.4 * ease.out(Math.min(1, k * 2))); if (k >= 1) { app.ticker.remove(f); g.destroy(); } }; app.ticker.add(f);
    gerbe(v.x, v.y, 14, couleur, .6, 9, 450);
  }

  // ---------------------------------------------------------------- les ultis
  async function barrage(c, avant, apres) {   // Miss Fortune : 4 vagues de boulets enflammés
    const vs = vivantsEnFace(c, avant); if (!vs.length) return;
    const src = { x: c.x, y: c.y + (c.u.camp === 0 ? -1 : 1) * c.dims.h * .3 };
    for (let v = 1; v <= 4; v++) {
      flash(src.x, src.y, c.dims.w * 1.3, 0xffb040); gerbe(src.x, src.y, 30, 0xffa030, .7, 8, 500);
      const arrivees = [];
      for (let i = 0; i < 17; i++) { const cible = vs[i % vs.length]; const vers = { x: cible.x + hasard(-cible.dims.w * .4, cible.dims.w * .4), y: cible.y + hasard(-cible.dims.h * .3, cible.dims.h * .3) };
        arrivees.push(boulet(src, vers, Math.abs(i - 8) * 8)); }
      await Promise.all(arrivees);
      secousse(v === 4 ? 14 : 7);
      vs.forEach((x) => toucher(x, [Math.round(avant[x.k][0] + (apres[x.k][0] - avant[x.k][0]) * v / 4), apres[x.k][1]]));
      await attendre(160);
    }
  }
  function boulet(de, vers, retard) {
    return new Promise((r) => {
      const s = new P.Graphics(); s.beginFill(0x1a1a1a); s.lineStyle(1.5, 0xf59b3a); s.drawCircle(0, 0, 7); s.endFill(); s.beginFill(0x8a7a66); s.drawCircle(-2, -2, 2.5); s.endFill();
      s.x = de.x; s.y = de.y; s.visible = false; fx.addChild(s); let t = -retard; const ms = hasard(360, 440);
      const f = () => { if (s.destroyed) { app.ticker.remove(f); r(); return; } t += app.ticker.deltaMS * vitesse; if (t < 0) return; s.visible = true; const k = Math.min(1, t / ms);
        s.x = de.x + (vers.x - de.x) * k; s.y = de.y + (vers.y - de.y) * k - Math.sin(k * Math.PI) * 50;
        particule({ x: s.x, y: s.y, taille: hasard(16, 26), fin: 4, vie: 260, couleur: k < .5 ? 0xffc040 : 0xff6a10, alpha: .8 });
        if (Math.random() < .4) particule({ x: s.x, y: s.y, vx: hasard(-.05, .05), vy: hasard(-.05, .05), taille: 4, vie: 400, couleur: 0xffd070 });
        if (k >= 1) { app.ticker.remove(f); s.destroy(); flash(vers.x, vers.y, 60, 0xff8a20, 260); gerbe(vers.x, vers.y, 6, 0xffa040, .35, 6, 380); r(); } };
      app.ticker.add(f);
    });
  }
  // Senna : l'animation du sort (tirée de la vidéo du tir, découpée en images) part de Senna vers les ennemis
  const SENNA = { bouche: [270 / 960, 400 / 540], impact: [780 / 960, 110 / 540], larg: 640, haut: 360, debut: 12, eclat: 35, fin: 47, ips: 15 };
  let framesSenna = null;
  function imagesSenna() {
    if (framesSenna) return framesSenna;
    const feuilles = (options.sennaFeuilles || []).map((u) => tex[u]).filter(Boolean);
    if (feuilles.length < 2) return null;
    framesSenna = [];
    feuilles.forEach((t) => { for (let i = 0; i < 24; i++) framesSenna.push(new P.Texture(t.baseTexture, new P.Rectangle((i % 6) * SENNA.larg, Math.floor(i / 6) * SENNA.haut, SENNA.larg, SENNA.haut))); });
    return framesSenna;
  }
  function tirSenna(src, cible, surEclat) {
    return new Promise((r) => {
      const fr = imagesSenna();
      // le point d'impact du sort est posé sur la cible ; le sort est tourné dans l'axe Senna → cible et assez grand pour remplir l'écran
      const s = new P.Sprite(fr[SENNA.debut]); s.anchor.set(...SENNA.impact); s.blendMode = P.BLEND_MODES.ADD; s.x = cible.x; s.y = cible.y;
      const dxv = (SENNA.impact[0] - SENNA.bouche[0]) * SENNA.larg, dyv = (SENNA.impact[1] - SENNA.bouche[1]) * SENNA.haut;
      const dist = Math.hypot(cible.x - src.x, cible.y - src.y);
      s.rotation = Math.atan2(cible.y - src.y, cible.x - src.x) - Math.atan2(dyv, dxv);
      s.scale.set(Math.max(dist / Math.hypot(dxv, dyv), Math.min(L, H * 1.4) * .95 / SENNA.larg));
      s.alpha = 0; fx.addChild(s);
      let t = 0, eclate = false;
      const duree = (SENNA.fin - SENNA.debut + 1) * 1000 / SENNA.ips;
      const f = () => {
        if (s.destroyed) { app.ticker.remove(f); r(); return; }
        t += app.ticker.deltaMS * vitesse;
        const i = Math.min(SENNA.fin, SENNA.debut + Math.floor(t * SENNA.ips / 1000));
        s.texture = fr[i];
        s.alpha = Math.min(1, t / 160) * (t > duree - 320 ? Math.max(0, (duree - t) / 320) : 1);
        if (!eclate && i >= SENNA.eclat) { eclate = true; surEclat(); }
        if (t >= duree) { app.ticker.remove(f); s.destroy(); r(); }
      };
      app.ticker.add(f);
    });
  }
  async function tenebres(c, avant, apres) {   // Senna : le tir de la relique, puis les bulles de bouclier
    const bouche = { x: c.x + c.dims.w * .18 * (c.u.camp === 0 ? 1 : -1), y: c.y + c.dims.h * (c.u.camp === 0 ? -.28 : .28) };
    for (let n = 0; n < 6; n++) {   // la charge : la lumière est aspirée vers la relique
      for (let i = 0; i < 12; i++) { const a = hasard(0, 6.28), d = hasard(90, 200), ms = hasard(320, 480), sombre = i % 3 === 0;
        particule({ x: bouche.x + Math.cos(a) * d, y: bouche.y + Math.sin(a) * d * .8, vx: -Math.cos(a) * d / ms, vy: -Math.sin(a) * d * .8 / ms, vie: ms,
          taille: sombre ? hasard(26, 46) : hasard(5, 10), fin: sombre ? 8 : 2, couleur: sombre ? 0x0b2a2a : 0x9ffff0, alpha: sombre ? .5 : 1 }); }
      halo(bouche.x, bouche.y, 40 + n * 16, 0x6fffe6, .5 + n * .06, 160);
      await attendre(70);
    }
    const vs = vivantsEnFace(c, avant); if (!vs.length) return;
    const cible = { x: vs.reduce((s, v) => s + v.x, 0) / vs.length, y: vs.reduce((s, v) => s + v.y, 0) / vs.length };
    secousse(8); halo(bouche.x, bouche.y, c.dims.w * 1.8, 0xd8fff8, 1, 300);
    const touche = () => { secousse(16); vs.forEach((v) => { halo(v.x, v.y, Math.min(v.dims.w, 320) * 1.6, 0xe0fffa, 1, 420); gerbe(v.x, v.y, 24, 0xbffff4, .7, 10, 700); toucher(v, apres[v.k]); }); };
    if (imagesSenna()) await tirSenna(bouche, cible, touche);
    else {   // secours si les images du sort n'ont pas pu se charger : l'ancien rayon de plasma
      const y = cible.y, epais = Math.max(...vs.map((v) => v.dims.h)) * (vs[0].u.boss ? .7 : 1.15);
      const plasma = rayonPlasma(L / 2, y, L * 1.2, epais, 0, 1300);
      await attendre(400); touche(); await plasma;
    }
    const allies = unites.filter((x) => x.u.camp === c.u.camp && !x.ko);
    for (const x of allies) {
      for (let i = 0; i < 22; i++) particule({ x: x.x + hasard(-x.dims.w * .5, x.dims.w * .5), y: x.y - x.dims.h * hasard(.7, 1.1), vy: hasard(.12, .22), vie: hasard(500, 800), taille: hasard(4, 8), fin: 2, couleur: 0xbff6ff });
      bulleBouclier(x, 0x5fd0ff);
    }
    await attendre(420);
    allies.forEach((x) => toucher(x, apres[x.k]));
    await attendre(600);
  }
  function rayonPlasma(x, y, longueur, epais, angle, ms) {
    return new Promise((r) => {
      const cont = new P.Container(); cont.x = x; cont.y = y; cont.rotation = angle; fx.addChild(cont);
      const couches = [[1.6, 0x0c6f66, .55, .6], [1, 0x2ff0d8, .9, 1.1], [.45, 0xffffff, 1, 1.8]];
      const rubans = couches.map(([h, teinte, al, v]) => { const t = new P.TilingSprite(PLASMA, 1024, 256); t.anchor.set(.5); t.width = longueur; t.height = epais * h;
        t.tint = teinte; t.blendMode = P.BLEND_MODES.ADD; t.alpha = 0; t.vitesseDefil = v; t.alphaMax = al; t.tileScale.set(1, (epais * h) / 256); cont.addChild(t); return t; });
      const fumee = new P.TilingSprite(PLASMA, 1024, 256); fumee.anchor.set(.5); fumee.width = longueur; fumee.height = epais * 2.4; fumee.tint = 0x000000; fumee.alpha = 0; fumee.tileScale.set(1.4, epais * 2.4 / 256);
      cont.addChildAt(fumee, 0);
      let t = 0;
      const f = () => {
        if (cont.destroyed) { app.ticker.remove(f); r(); return; }
        t += app.ticker.deltaMS * vitesse; const k = Math.min(1, t / ms), monte = ease.out(Math.min(1, k / .12)), al = k < .65 ? 1 : 1 - (k - .65) / .35;
        rubans.forEach((rb, i) => { rb.tilePosition.x -= rb.vitesseDefil * app.ticker.deltaMS * vitesse; rb.alpha = rb.alphaMax * al; rb.scale.y = monte * (1 + .12 * Math.sin(t * .04 + i)); rb.width = longueur; });
        fumee.tilePosition.x -= .4 * app.ticker.deltaMS * vitesse; fumee.alpha = .55 * al; fumee.scale.y = monte * (1 + .08 * Math.sin(t * .03));
        if (k >= 1) { app.ticker.remove(f); cont.destroy({ children: true }); r(); }
      };
      app.ticker.add(f);
    });
  }
  function bulleBouclier(x, couleur, duree = 1700) {
    const b = new P.Sprite(BULLE); b.anchor.set(.5); b.blendMode = P.BLEND_MODES.ADD; b.tint = couleur; b.x = x.x; b.y = x.y; fx.addChild(b);
    const reflet = new P.Sprite(REFLET); reflet.anchor.set(.5); reflet.blendMode = P.BLEND_MODES.ADD; reflet.x = x.x; reflet.y = x.y; fx.addChild(reflet);
    const lw = x.dims.w * 1.45, lh = x.dims.h * 1.18; let t = 0;
    const f = () => { if (b.destroyed) { app.ticker.remove(f); return; } t += app.ticker.deltaMS * vitesse; const k = Math.min(1, t / duree), monte = ease.back(Math.min(1, k / .2)), al = k < .7 ? 1 : 1 - (k - .7) / .3;
      const respire = 1 + .03 * Math.sin(t * .006);
      b.width = lw * monte * respire; b.height = lh * monte * respire; b.alpha = .95 * al;
      reflet.width = lw * monte * .96; reflet.height = lh * monte * .96; reflet.rotation = t * .0015; reflet.alpha = .7 * al;
      if (k >= 1) { app.ticker.remove(f); b.destroy(); reflet.destroy();
        for (let i = 0; i < 14; i++) { const a = hasard(0, 6.28); particule({ x: x.x + Math.cos(a) * lw * .45, y: x.y + Math.sin(a) * lh * .45, vx: Math.cos(a) * .1, vy: Math.sin(a) * .1, vie: 450, taille: 7, fin: 1, couleur: 0xd8f6ff }); } } };
    app.ticker.add(f);
  }
  async function contreAttaque(c, avant, apres) {   // Jax : garde, bond, impact qui fend le sol
    const t = cibles(c, avant, apres)[0] || vivantsEnFace(c, avant)[0]; if (!t) return;
    const tourbillon = new P.Graphics(); tourbillon.blendMode = P.BLEND_MODES.ADD; fx.addChild(tourbillon); let tt = 0;
    const tourne = () => { if (tourbillon.destroyed) { app.ticker.remove(tourne); return; } tt += app.ticker.deltaMS * vitesse; tourbillon.clear(); const R = c.dims.w * .62;
      for (let i = 0; i < 3; i++) { const a = tt * .016 + i * 2.094; tourbillon.lineStyle(10 - i * 2, 0xffd36a, .55); tourbillon.arc(c.x, c.y, R, a, a + 1.4);
        tourbillon.lineStyle(3, 0xffffff, .9); tourbillon.arc(c.x, c.y, R, a + 1.1, a + 1.4);
        particule({ x: c.x + Math.cos(a + 1.4) * R, y: c.y + Math.sin(a + 1.4) * R, taille: 26, fin: 4, vie: 200, couleur: 0xffe08a, alpha: .8 }); } };
    app.ticker.add(tourne);
    for (let i = 0; i < 5; i++) { const a = hasard(0, 6.28); gerbe(c.x + Math.cos(a) * c.dims.w * .62, c.y + Math.sin(a) * c.dims.w * .62, 8, 0xfff0c0, .5, 6, 300); await attendre(110); }
    app.ticker.remove(tourne); tourbillon.destroy();
    c.enMouvement = true;
    await tween(c.scale, { x: 1.06, y: .9 }, 140, ease.out);
    const sommet = { x: (c.x + t.x) / 2, y: Math.min(c.y, t.y) - c.dims.h * .55 };
    const traine = setInterval(() => { if (!c.destroyed) remanence(c); }, 35);
    gerbe(c.x, c.y + c.dims.h * .45, 24, 0xc8b08a, .4, 18, 600, .0008);
    tween(c.scale, { x: 1.1, y: 1.1 }, 200);
    await tween(c, { x: sommet.x, y: sommet.y }, 300, ease.out);
    c.rotation = -.35;
    await tween(c, { x: t.x, y: t.y + t.dims.h * .35 }, 170, (k) => k * k * k);
    clearInterval(traine);
    const sol = { x: t.x, y: t.y + t.dims.h * .45 };
    secousse(22); flash(sol.x, sol.y, Math.min(t.dims.w, 260) * 2.2, 0xfff4d0, 260); flash(t.x, t.y, Math.min(t.dims.w, 300) * 1.6, 0xffcf60, 420);
    onde(sol.x, sol.y, Math.min(t.dims.w, 300) * 2.2, 0xffd070, 700, 12); onde(sol.x, sol.y, Math.min(t.dims.w, 300) * 1.4, 0xffffff, 420, 5);
    fissures(sol, Math.min(t.dims.w, 260) * 1.5); debris(sol, 26); poussiere(sol, Math.min(t.dims.w, 220));
    c.scale.set(1.18, .92); tween(c.scale, { x: 1.1, y: 1.1 }, 160, ease.back);
    toucher(t, apres[t.k]); etoiles(t);
    await attendre(380);
    c.rotation = 0; tween(c.scale, { x: 1, y: 1 }, 300);
    await tween(c, { x: c.base.x, y: c.base.y }, 420, ease.inout); c.enMouvement = false;
    bulleBouclier(c, 0x8fc4ff, 1400);
    unites.forEach((x) => { if (x !== t) toucher(x, apres[x.k]); });
    await attendre(300);
  }
  function remanence(c) {
    const s = new P.Sprite(c.img.texture); s.anchor.set(.5); s.scale.set(c.img.scale.x * c.scale.x); s.x = c.x; s.y = c.y; s.rotation = c.rotation;
    s.tint = 0xffc860; s.alpha = .45; s.blendMode = P.BLEND_MODES.ADD; derriere.addChild(s);
    tween(s, { alpha: 0 }, 260).then(() => { if (!s.destroyed) s.destroy(); });
  }
  function fissures(o, R) {
    const g = new P.Graphics(); g.blendMode = P.BLEND_MODES.ADD; fx.addChild(g); const lignes = [];
    for (let i = 0; i < 9; i++) { let a = hasard(0, 6.28), x = o.x, y = o.y; const pts = [[x, y]];
      for (let s = 0; s < 5; s++) { a += hasard(-.5, .5); const d = R * hasard(.12, .25); x += Math.cos(a) * d; y += Math.sin(a) * d * .45; pts.push([x, y]); } lignes.push(pts); }
    let t = 0; const f = () => { if (g.destroyed) { app.ticker.remove(f); return; } t += app.ticker.deltaMS * vitesse; const k = Math.min(1, t / 1100), pousse = ease.out(Math.min(1, k / .2)), al = k < .4 ? 1 : 1 - (k - .4) / .6; g.clear();
      for (const pts of lignes) { const n = Math.max(2, Math.ceil(pts.length * pousse));
        for (const [larg, coul, a2] of [[7, 0xff8a20, .5], [2.5, 0xfff0c0, 1]]) { g.lineStyle(larg, coul, a2 * al); g.moveTo(...pts[0]); for (let i = 1; i < n; i++) g.lineTo(...pts[i]); } }
      if (k >= 1) { app.ticker.remove(f); g.destroy(); } }; app.ticker.add(f);
  }
  function debris(o, n) {
    for (let i = 0; i < n; i++) {
      const g = new P.Graphics(); const r = hasard(4, 11); g.beginFill([0x5a4a3a, 0x3a2f26, 0x7a6650][i % 3]); g.moveTo(-r, -r * .4); g.lineTo(r * .3, -r); g.lineTo(r, r * .2); g.lineTo(-r * .2, r); g.endFill();
      g.x = o.x; g.y = o.y; fx.addChild(g);
      const a = hasard(-Math.PI * .95, -Math.PI * .05), v = hasard(.35, .85); let vx = Math.cos(a) * v, vy = Math.sin(a) * v; const vr = hasard(-.02, .02); let t = 0;
      const f = () => { if (g.destroyed) { app.ticker.remove(f); return; } const dt = app.ticker.deltaMS * vitesse; t += dt; vy += .0022 * dt; g.x += vx * dt; g.y += vy * dt; g.rotation += vr * dt; g.alpha = Math.max(0, 1 - t / 900);
        if (t > 900) { app.ticker.remove(f); g.destroy(); } }; app.ticker.add(f);
    }
  }
  function poussiere(o, w) {
    for (let i = 0; i < 30; i++) { const s = new P.Sprite(POINT); s.anchor.set(.5); s.tint = 0x8a7a66; s.alpha = .35; s.x = o.x + hasard(-w * .3, w * .3); s.y = o.y + hasard(-10, 10);
      const z = hasard(w * .3, w * .6); s.width = s.height = z; fx.addChild(s); const vx = hasard(-.35, .35), vy = hasard(-.12, -.02); let t = 0;
      const f = () => { if (s.destroyed) { app.ticker.remove(f); return; } const dt = app.ticker.deltaMS * vitesse; t += dt; s.x += vx * dt * (1 - t / 1600); s.y += vy * dt; s.width = s.height = z * (1 + t / 900); s.alpha = .35 * Math.max(0, 1 - t / 1600);
        if (t > 1600) { app.ticker.remove(f); s.destroy(); } }; app.ticker.add(f); }
  }
  function etoiles(t) {
    const st = []; for (let i = 0; i < 4; i++) { const s = new P.Text("★", new P.TextStyle({ fontSize: Math.max(18, Math.min(t.dims.w, 300) * .14), fill: [0xfff6c0, 0xffc020], stroke: 0x5a3a00, strokeThickness: 2, dropShadow: true, dropShadowBlur: 8, dropShadowDistance: 0, dropShadowColor: 0xffb000 })); s.anchor.set(.5); fx.addChild(s); st.push(s); }
    let tt = 0; const f = () => { if (st[0].destroyed) { app.ticker.remove(f); return; } tt += app.ticker.deltaMS * vitesse; st.forEach((s, i) => { const a = tt * .007 + i * 1.571; s.x = t.x + Math.cos(a) * Math.min(t.dims.w, 300) * .4; s.y = t.y - t.dims.h * .48 + Math.sin(a) * t.dims.h * .05; s.scale.set(.8 + .25 * Math.sin(a)); s.alpha = Math.min(1, (1700 - tt) / 300);
        if (Math.random() < .2) particule({ x: s.x, y: s.y, taille: 6, fin: 1, vie: 300, couleur: 0xffe080 }); });
      if (tt > 1700) { app.ticker.remove(f); st.forEach((s) => s.destroy()); } }; app.ticker.add(f);
  }
  async function souffle(c, avant, apres) {   // Drake : une vague de feu sur toute l'équipe
    const vs = vivantsEnFace(c, avant); if (!vs.length) return;
    const src = { x: c.x, y: c.y + c.dims.h * .25 * (c.u.camp === 1 ? 1 : -1) };
    await tween(c.corps.scale, { x: 1.05, y: 1.05 }, 300, ease.out);
    const xs = vs.map((v) => v.x), xmin = Math.min(...xs) - vs[0].dims.w * .6, xmax = Math.max(...xs) + vs[0].dims.w * .6, yc = vs[0].y;
    for (let n = 0; n < 16; n++) {
      for (let i = 0; i < 22; i++) { const tx = hasard(xmin, xmax), ms = hasard(450, 650);
        particule({ x: src.x + hasard(-40, 40), y: src.y, vx: (tx - src.x) / ms, vy: (yc - src.y) / ms, vie: ms + 250, taille: hasard(40, 80), fin: 120, couleur: [0xffd060, 0xff8a20, 0xff4a10][i % 3], alpha: .55, frein: .995 }); }
      if (n === 6) secousse(18);
      await attendre(55);
    }
    await attendre(260);
    vs.forEach((v) => { flash(v.x, v.y, v.dims.w * 2, 0xff5a10, 450); gerbe(v.x, v.y, 20, 0xff9a30, .6, 12, 700); toucher(v, apres[v.k]); });
    secousse(14); c.corps.scale.set(1);
    await attendre(500);
  }
  async function ultiGenerique(c, avant, apres) {
    onde(c.x, c.y, c.dims.w * 2, c.u.camp === 0 ? 0xffd070 : 0xff5040, 700, 8); gerbe(c.x, c.y, 40, c.u.camp === 0 ? 0xffd070 : 0xff5040, .8, 10, 700);
    await attendre(300); apres.forEach((e, k) => toucher(unites[k], e));
  }
  const ULTIS = [[/Barrage de balles/, barrage], [/Ténèbres aveuglantes/, tenebres], [/Contre-attaque/, contreAttaque], [/Souffle dévastateur/, souffle]];

  async function entreeBoss(c) {   // le cadre du boss s'embrase
    const { w, h } = c.dims, x0 = c.x - w / 2, y0 = c.y - h / 2;
    const bord = () => { const cote = Math.random();
      if (cote < .5) return { x: x0 + Math.random() * w, y: y0 + h * .92 };
      if (cote < .75) return { x: x0 + w * .06, y: y0 + Math.random() * h };
      return { x: x0 + w * .94, y: y0 + Math.random() * h }; };
    halo(c.x, c.y, w * 1.4, 0xff5a10, .6, 700);
    for (let n = 0; n < 22; n++) {
      for (let i = 0; i < 16; i++) { const p = bord(); particule({ x: p.x, y: p.y, vx: hasard(-.03, .03), vy: hasard(-.28, -.12), vie: hasard(500, 900), taille: hasard(30, 70), fin: 6, couleur: [0xffd060, 0xff8a20, 0xff4010][i % 3], alpha: .6, frein: .99 }); }
      for (let i = 0; i < 4; i++) { const p = bord(); particule({ x: p.x, y: p.y, vx: hasard(-.05, .05), vy: hasard(-.35, -.18), vie: hasard(900, 1500), taille: hasard(4, 7), fin: 1, couleur: 0xffc060 }); }
      if (n === 8) { secousse(16); c.corps.scale.set(1.04); tween(c.corps.scale, { x: 1, y: 1 }, 300); }
      await attendre(45);
    }
    await attendre(450);
  }

  // ---------------------------------------------------------------- le déroulé
  function ligneTexte(l) { const p = dlg.querySelector(".a3-ligne"); p.textContent = l || ""; }
  async function derouler(moi) {
    let avant = combat.unites.map((u) => [u.pv, u.bouclier, u.jauge]);
    for (const c of unites) { c.alpha = 0; c.y = c.base.y + (c.u.camp === 0 ? 80 : -80); tween(c, { alpha: 1, y: c.base.y }, 600, ease.back); }
    await attendre(700); if (moi !== jeton) return;
    const boss = unites.find((c) => c.u.boss); if (boss && !calme()) await entreeBoss(boss);
    for (const a of combat.actions) {
      if (moi !== jeton) return;
      dlg.querySelector("#a3-tour").textContent = "Tour " + a.t;
      const c = unites[a.a], apres = a.e.map((e) => [e[0], e[1], e[2]]);
      const ligne = a.l.find((l) => /^(✨|🔥)/u.test(l));
      const lisible = a.l.filter((l) => !l.startsWith("💫") || a.passe);
      if (lisible.length) ligneTexte(lisible[lisible.length - 1]);
      if (a.passe) { gerbe(c.x, c.y - c.dims.h * .45, 10, 0xffe27a, .2, 8, 600); apres.forEach((e, k) => toucher(unites[k], e, true)); await attendre(250); }
      else if (ligne) {
        const m = ligne.match(/lance (.+?)(?: :| sur |,|$)/); await annoncer(m ? m[1] : "Ulti !", c.u.camp);
        if (moi !== jeton) return;
        const fin = await mettreEnAvant(c); await attendre(250);
        const e = (ULTIS.find(([re]) => re.test(ligne)) || [0, ultiGenerique])[1];
        finAnnonce(); await (calme() ? ultiGenerique : e)(c, avant, apres); await fin();
        if (moi !== jeton) return;
        apres.forEach((x, k) => { const u = unites[k]; if (u.pv !== x[0]) toucher(u, x); else { u.bouclier = x[1]; u.jaugeV = x[2]; dessinerPv(u); } });
        await attendre(300);
      } else await attaqueSimple(c, avant, apres);
      apres.forEach((x, k) => { const u = unites[k]; if (u && !u.destroyed) { u.jaugeV = x[2]; dessinerPv(u); } });
      avant = apres; await attendre(240);
    }
    if (moi !== jeton) return;
    if (combat.fin) ligneTexte(combat.fin);
    await celebrer(combat.victoire);
  }
  async function celebrer(victoire) {
    voile.clear(); voile.beginFill(0x000000); voile.drawRect(-50, -50, L + 100, H + 100); voile.endFill(); tween(voile, { alpha: .45 }, 500);
    const r = new P.Sprite(RAYONS); r.anchor.set(.5); r.blendMode = P.BLEND_MODES.ADD; r.tint = victoire ? 0xffcf70 : 0xff3a2a; r.x = L / 2; r.y = H / 2; r.width = r.height = Math.max(L, H) * 1.2; r.alpha = 0; hud.addChild(r);
    const tourne = () => { if (r.destroyed) { app.ticker.remove(tourne); return; } r.rotation += .0004 * app.ticker.deltaMS; }; app.ticker.add(tourne);
    tween(r, { alpha: victoire ? .55 : .3 }, 700);
    for (let i = 0; i < (calme() ? 0 : 160); i++) particule({ x: hasard(0, L), y: hasard(-40, H * .3), vx: hasard(-.03, .03), vy: hasard(.05, .16), vie: hasard(2000, 4000), taille: hasard(4, 9), fin: 2,
      couleur: victoire ? [0xffd070, 0xfff0c0, 0xffa040][i % 3] : 0x9a2a20, calque: hud });
    secousse(victoire ? 10 : 6);
    await attendre(600);
    montrerFin();
  }
  function montrerFin() {
    const f = dlg.querySelector("#a3-fin");
    if (options.fin) options.fin(f);
    f.hidden = false;
  }
  function passer() {   // fin immédiate : on pose le résultat final sans animation
    if (!combat) return;
    jeton++;
    finAnnonce();
    const der = combat.actions[combat.actions.length - 1];
    if (der) { der.e.forEach((e, k) => { const u = unites[k]; if (u) { u.fige = true; u.alpha = 1; if (!u.enMouvement) { u.x = u.base.x; u.y = u.base.y; } toucher(u, e, true); } });
      dlg.querySelector("#a3-tour").textContent = "Tour " + der.t; }
    if (combat.fin) ligneTexte(combat.fin);
    const moi = jeton; vitesse = 4;
    celebrer(combat.victoire).then(() => { if (moi === jeton) { vitesse = 1; boutonsVitesse(); } });
  }

  function chargerImage(url) {
    return new Promise((ok) => { if (!url || tex[url]) return ok();
      const im = new Image(); im.onload = () => { tex[url] = P.Texture.from(im); ok(); }; im.onerror = () => ok(); im.src = url; });
  }

  window.ArenePixi = {
    disponible() { try { return !!window.PIXI && P.utils.isWebGLSupported(); } catch (e) { return false; } },
    /** joue un combat de la tour. opts : titre (html), icones(u) -> [url], fin(element) remplit l'écran de fin, fond, cadreBoss, barreBoss */
    async jouer(c, opts) {
      if (!preparer()) return false;
      options = opts || {};
      const moi = ++jeton;
      nettoyer();
      combat = c; vitesse = 1; boutonsVitesse();
      dlg.querySelector("#a3-titre").innerHTML = (options.titre || "") + ` <span id="a3-tour">Tour 1</span>`;
      const f = dlg.querySelector("#a3-fin"); f.hidden = true; f.innerHTML = "";
      ligneTexte("");
      if (!dlg.open) dlg.showModal();
      app.start(); app.resize();
      const urls = new Set([options.fond, options.cadreBoss, options.barreBoss, ...(options.sennaFeuilles || [])]);
      c.unites.forEach((u) => { urls.add(u.image); (options.icones ? options.icones(u) : []).forEach((x) => urls.add(x)); });
      await Promise.all([...urls].map(chargerImage));
      try { await Promise.all([document.fonts.load("900 40px Cinzel"), document.fonts.load("700 20px Barlow")]); } catch (e) { /* les polices de secours suffisent */ }
      if (moi !== jeton) return true;
      fond.texture = tex[options.fond] || P.Texture.EMPTY;
      unites = c.unites.map(creerUnite);
      unites.forEach((u) => { u.jaugeV = u.u.jauge; });
      app.resize(); placer();
      derouler(moi);
      return true;
    },
    element() { return dlg; },
    fermer() { if (dlg && dlg.open) dlg.close(); }
  };
})();
