/* 2Hot4Deck · la jungle sur le site : la carte de 16 buissons du bot, dessinée en clairière de nuit.
   Les règles et le butin sont calculés par le serveur (le code du bot) ; cette page ne fait que montrer.
   Le contenu des buissons cachés n'est jamais envoyé à la page : impossible de tricher en regardant le code. */

const JGL = { infos: null, carte: null, occupe: false, smite: null, mise: 1, fond: null };
const MONSTRE_IMG = { "Gromp": "gromp", "Loup des ténèbres": "loup", "Corbin écarlate": "corbin", "Golem ancien": "golem", "Sentinelle bleue": "sentinelle", "Roncier rouge": "roncier" };
const imgJgl = (nom) => `/static/jgl_${nom}.webp`;
const CONTENU = {
  camp: ["🐺", "Camp"], bleu: ["🔵", "Sentinelle bleue"], rouge: ["🔴", "Roncier rouge"], tresor: ["💰", "Trésor"],
  gank: ["⚔️", "Gank"], fruit: ["🍯", "Fruit de miel"], vide: ["🍃", "Rien"], coffre: ["🧰", "Coffre hextech"], balise: ["👁️", "Balise"],
};
const enMinutes = (s) => { const h = Math.floor(s / 3600), m = Math.ceil((s % 3600) / 60); return h ? `${h} h ${String(m).padStart(2, "0")}` : `${m} min`; };

async function pageJungle() {
  const box = $("j-jungle");
  if (!moi) { box.innerHTML = `<div class="message">Connecte-toi avec Discord pour explorer la jungle.<div class="actions">${boutonConnexion()}</div></div>`; return; }
  if (!JGL.infos) {
    box.innerHTML = `<p class="nb">Chargement…</p>`;
    const r = ENDEMO ? { ok: true, d: jungleDemo.etat() } : await api("/api/jungle").catch(() => ({ ok: false }));
    if (!r.ok) { box.innerHTML = `<p class="nb">${esc(r.d?.erreur || "La jungle n'est pas disponible pour l'instant.")}</p>`; return; }
    JGL.infos = r.d; JGL.carte = r.d.carte; JGL.recu = performance.now();
  }
  dessinerJungle();
}

function dessinerJungle() {
  const box = $("j-jungle"), i = JGL.infos;
  if (!box) return;
  const ferme = i.niveau < i.requis;
  JGL.mise = Math.max(1, Math.min(JGL.mise, i.mise_max));
  const eclairs = Array.from({ length: i.max }, (_, k) => `<i class="${k < i.charges ? "plein" : ""}"></i>`).join("");
  const bandeau = `<section class="panneau jgl-bandeau">
      <div class="jgl-charges"><p class="tour-sur">Charges de Châtiment</p><div class="jgl-eclairs" aria-label="${i.charges} sur ${i.max}">${eclairs}</div>
        <p class="d-recharge">${i.prochaine == null ? "Stock plein" : `+1 dans <b>${enMinutes(i.prochaine)}</b>`} · ${nombre(i.chasses)} camps nettoyés${i.bonus ? ` · <b>+${i.bonus} %</b> de butin` : ""}</p></div>
      <div class="jgl-actions">
        ${i.mise_limite > 1 ? `<label class="jgl-mise">Mise<select id="jgl-mise">${Array.from({ length: i.mise_limite }, (_, k) => `<option value="${k + 1}"${k + 1 === JGL.mise ? " selected" : ""}${k + 1 > i.charges ? " disabled" : ""}>${k + 1} charge${k ? "s" : ""} · butin ×${k + 1}</option>`).join("")}</select></label>` : ""}
        <button class="bouton grand" id="jgl-explorer"${ferme || !i.charges || (JGL.carte && !JGL.carte.fini) ? " disabled" : ""}><i class="orne g"></i>Explorer la jungle<i class="orne d"></i></button>
        <button class="bouton secondaire" id="jgl-rapide"${ferme || !i.charges || (JGL.carte && !JGL.carte.fini) ? " disabled" : ""} title="Sans jouer : ${i.rapide_pct} % du butin d'un clear complet"><i class="orne g"></i>Clear rapide<i class="orne d"></i></button>
      </div>
      <p class="jgl-promesse">Une charge = une carte. Un clear complet rapporte jusqu'à <b>✨ ${nombre(i.clear_xp * JGL.mise)}</b> XP par carte et <b>💰 ${nombre(i.clear_golds * JGL.mise)}</b> golds ; le clear rapide en donne ${i.rapide_pct} % sans jouer.</p>
    </section>
    ${ferme ? `<div class="message">🔒 La jungle s'ouvre au <b>niveau ${i.requis}</b> de compte (tu es niveau ${i.niveau}).</div>` : ""}`;
  box.innerHTML = bandeau + `<div id="jgl-zone">${JGL.carte ? "" : accueilJungle()}</div>`;
  if (JGL.carte) dessinerCarte(false);
  if ($("jgl-mise")) $("jgl-mise").onchange = (e) => { JGL.mise = Number(e.target.value); dessinerJungle(); };
  $("jgl-explorer").onclick = () => agir("explorer", JGL.mise);
  $("jgl-rapide").onclick = () => agir("rapide", JGL.mise);
}

function accueilJungle() {
  return `<section class="panneau jgl-regles">
    <h2>Comment ça marche</h2>
    <ul>
      <li><span>🌿</span>16 buissons cachent des <b>camps</b>, le <b>Bleu</b> et le <b>Rouge</b>, des <b>trésors</b>, un <b>fruit de miel</b>… et <b>3 ganks</b>.</li>
      <li><span>🔢</span>Un buisson fouillé affiche le nombre de ganks cachés autour de lui. Ton premier buisson n'est jamais un gank.</li>
      <li><span>👣</span>Dès ton 2e buisson, les ganks se déplacent d'une case après chaque fouille : les chiffres changent.</li>
      <li><span>⚡</span>Sur le Bleu et le Rouge, place ton <b>Châtiment</b> quand sa vie passe dans la zone dorée : gros butin si c'est réussi.</li>
      <li><span>💀</span>Au 2e gank, ton équipe rentre à la base avec ce qu'elle a ramassé. S'il ne reste que des ganks : <b>clear complet</b>, +20 % de butin.</li>
    </ul></section>`;
}

// ---------- le plateau ----------
function positionBuisson(k, cote) {   // une grille un peu désordonnée, pour que ça ressemble à une clairière
  const x = k % cote, y = Math.floor(k / cote);
  const bruit = (n) => (Math.sin(n * 12.9898 + 78.233) * 43758.5453) % 1;
  const jx = (bruit(k + 1) - 0.5) * 5, jy = (bruit(k + 7) - 0.5) * 5;
  return { left: 14 + x * 24 + jx, top: 15 + y * 23 + jy };
}

function dessinerCarte(animer, ancien) {
  const c = JGL.carte, zone = $("jgl-zone");
  if (!c) { zone.innerHTML = accueilJungle(); return; }
  if (!$("jgl-plateau")) {
    zone.innerHTML = `<div class="jgl-jeu">
      <div class="jgl-plateau" id="jgl-plateau" role="grid" aria-label="La carte de la jungle">
        <canvas id="jgl-fond" aria-hidden="true"></canvas><div class="jgl-lucioles" aria-hidden="true">${Array.from({ length: 18 }, (_, k) => `<i style="--x:${(k * 37) % 100}%;--y:${(k * 53) % 100}%;--d:${4 + (k % 5)}s;--r:${(k % 7) * -0.9}s"></i>`).join("")}</div>
        <div class="jgl-buissons" id="jgl-buissons"></div>
        <div class="jgl-flash" id="jgl-flash"></div>
      </div>
      <aside class="jgl-hud">
        <div class="jgl-vies" id="jgl-vies"></div>
        <div class="jgl-butin"><div><span>✨ XP par carte</span><b id="jgl-xp">0</b></div><div><span>💰 Golds</span><b id="jgl-golds">0</b></div></div>
        <ol class="jgl-journal" id="jgl-journal" aria-live="polite"></ol>
        <button class="bouton secondaire" id="jgl-rentrer"><i class="orne g"></i>🏠 Rentrer à la base<i class="orne d"></i></button>
      </aside>
    </div>`;
    peindreFond();
    $("jgl-rentrer").onclick = () => agir("rentrer");
    requestAnimationFrame(() => $("jgl-plateau")?.scrollIntoView({ block: "center", behavior: calme() ? "auto" : "smooth" }));
  }
  const b = $("jgl-buissons");
  b.innerHTML = c.cases.map((x, k) => {
    const pos = positionBuisson(k, c.cote);
    const style = `left:${pos.left}%;top:${pos.top}%;--k:${k}`;
    if (!x.vu) return `<button class="buisson${x.repere ? " repere" : ""}" data-k="${k}" style="${style}" role="gridcell" aria-label="Buisson caché${x.repere ? ", gank repéré" : ""}"${c.fini || c.chatiment ? " disabled" : ""}>${touffe(k)}</button>`;
    const [emo, nom] = CONTENU[x.cle] || ["❔", x.cle];
    const tete = x.cle === "bleu" ? "sentinelle" : x.cle === "rouge" ? "roncier" : x.cle === "camp" ? (MONSTRE_IMG[x.monstre] || "loup") : null;
    const portrait = tete ? `<img src="${imgJgl("p_" + tete)}" alt="">` : `<span class="emo-c">${emo}</span>`;
    return `<div class="case ${x.cle}${x.n ? " danger n" + Math.min(x.n, 3) : ""}" data-k="${k}" style="${style}" role="gridcell" aria-label="${nom}, ${x.n} gank${x.n > 1 ? "s" : ""} autour">
      <div class="case-fond">${portrait}</div><span class="chiffre">${x.n}</span></div>`;
  }).join("");
  b.querySelectorAll(".buisson").forEach((el) => (el.onclick = () => agir("fouiller", Number(el.dataset.k))));
  $("jgl-vies").innerHTML = `<span>Ganks</span>${Array.from({ length: c.vies_max }, (_, k) => `<i class="${k < c.vies_max - c.vies ? "pris" : ""}" title="${k < c.vies_max - c.vies ? "Gank encaissé" : "Encore debout"}">⚔️</i>`).join("")}`;
  compter($("jgl-xp"), ancien ? ancien.xp : c.xp, c.xp);
  compter($("jgl-golds"), ancien ? ancien.golds : c.golds, c.golds);
  $("jgl-journal").innerHTML = c.journal.slice(-5).map((l) => `<li>${esc(l)}</li>`).join("");
  $("jgl-rentrer").hidden = !!c.fini;
  if (animer && c.evenement) jouerEvenement(c.evenement, ancien);
  if (c.chatiment && !JGL.smite) lancerChatiment(c.chatiment);
  if (c.fini) setTimeout(() => finCarte(c), animer ? 1100 : 0);
}

function touffe(k) {   // une touffe d'herbe haute dessinée en SVG, un peu différente pour chaque buisson
  const brins = [];
  for (let i = 0; i < 11; i++) {
    const x = 12 + i * 7.6 + Math.sin(k * 3 + i) * 2, h = 46 + ((k * 7 + i * 13) % 26), pen = ((i % 5) - 2) * 5 + Math.sin(k + i) * 4;
    brins.push(`<path d="M${x - 4} 96 Q${x + pen * 0.4} ${96 - h * 0.6} ${x + pen} ${96 - h} Q${x + pen * 0.3 + 2} ${96 - h * 0.55} ${x + 4} 96Z" fill="url(#h${i % 3})"/>`);
  }
  return `<svg viewBox="0 0 100 100" aria-hidden="true"><defs>
    <linearGradient id="h0" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#0b2a17"/><stop offset="1" stop-color="#3f8f4a"/></linearGradient>
    <linearGradient id="h1" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#0e321b"/><stop offset="1" stop-color="#5aa85a"/></linearGradient>
    <linearGradient id="h2" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#082214"/><stop offset="1" stop-color="#2f7a46"/></linearGradient></defs>
    <ellipse cx="50" cy="94" rx="44" ry="7" fill="#000" opacity=".45"/>${brins.join("")}</svg>`;
}

function peindreFond() {   // la clairière : sol de mousse, chemin de terre, rivière, ombres des arbres, brume
  const cv = $("jgl-fond"); if (!cv) return;
  const r = cv.getBoundingClientRect(), d = Math.min(devicePixelRatio || 1, 2);
  cv.width = Math.round(r.width * d); cv.height = Math.round(r.height * d);
  const x = cv.getContext("2d"), W = cv.width, H = cv.height;
  const g = x.createRadialGradient(W * 0.5, H * 0.45, 0, W * 0.5, H * 0.5, Math.max(W, H) * 0.75);
  g.addColorStop(0, "#1d3a24"); g.addColorStop(0.55, "#10261a"); g.addColorStop(1, "#050d09");
  x.fillStyle = g; x.fillRect(0, 0, W, H);
  let s = 7; const alea = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < 260; i++) {   // taches de mousse et d'herbe
    const px = alea() * W, py = alea() * H, rr = (8 + alea() * 40) * d;
    x.fillStyle = `rgba(${40 + alea() * 40 | 0},${80 + alea() * 60 | 0},${40 + alea() * 30 | 0},${0.06 + alea() * 0.1})`;
    x.beginPath(); x.ellipse(px, py, rr, rr * 0.6, alea() * 3, 0, 6.3); x.fill();
  }
  x.lineCap = "round";   // le chemin de terre qui serpente
  for (const [larg, coul] of [[60, "rgba(60,44,26,.55)"], [40, "rgba(92,70,42,.45)"], [16, "rgba(140,112,70,.25)"]]) {
    x.strokeStyle = coul; x.lineWidth = larg * d; x.beginPath(); x.moveTo(-20, H * 0.8);
    x.bezierCurveTo(W * 0.3, H * 0.95, W * 0.35, H * 0.35, W * 0.6, H * 0.45); x.bezierCurveTo(W * 0.8, H * 0.52, W * 0.9, H * 0.15, W + 20, H * 0.08); x.stroke();
  }
  const riv = x.createLinearGradient(0, 0, W, 0);   // un filet de rivière dans le coin
  riv.addColorStop(0, "rgba(40,120,150,.0)"); riv.addColorStop(0.5, "rgba(60,160,190,.35)"); riv.addColorStop(1, "rgba(40,120,150,.0)");
  x.strokeStyle = riv; x.lineWidth = 26 * d; x.beginPath(); x.moveTo(W * 0.55, H + 10); x.bezierCurveTo(W * 0.7, H * 0.8, W * 0.9, H * 0.9, W + 10, H * 0.7); x.stroke();
  for (let i = 0; i < 14; i++) {   // l'ombre des grands arbres sur les bords
    const bord = i % 4, px = bord === 0 ? 0 : bord === 1 ? W : alea() * W, py = bord === 2 ? 0 : bord === 3 ? H : alea() * H;
    const o = x.createRadialGradient(px, py, 0, px, py, (120 + alea() * 160) * d);
    o.addColorStop(0, "rgba(0,0,0,.75)"); o.addColorStop(1, "rgba(0,0,0,0)"); x.fillStyle = o; x.fillRect(0, 0, W, H);
  }
  const lune = x.createRadialGradient(W * 0.7, H * 0.2, 0, W * 0.7, H * 0.2, W * 0.5);   // un rayon de lune bleuté
  lune.addColorStop(0, "rgba(140,190,255,.14)"); lune.addColorStop(1, "rgba(140,190,255,0)"); x.fillStyle = lune; x.fillRect(0, 0, W, H);
}
addEventListener("resize", () => { if ($("jgl-fond")) peindreFond(); });

function compter(el, de, a) {
  if (!el) return;
  if (calme() || de === a) { el.textContent = nombre(a); return; }
  const t0 = performance.now(), duree = 700;
  const pas = (t) => { const k = Math.min(1, (t - t0) / duree); el.textContent = nombre(Math.round(de + (a - de) * (1 - (1 - k) ** 3))); if (k < 1) requestAnimationFrame(pas); };
  requestAnimationFrame(pas);
}

// ---------- les actions ----------
async function agir(action, valeur) {
  if (JGL.occupe) return;
  JGL.occupe = true;
  const ancien = JGL.carte ? { xp: JGL.carte.xp, golds: JGL.carte.golds } : null;
  try {
    let d;
    if (ENDEMO) d = { jungle: jungleDemo.agir(action, valeur) };
    else {
      const r = await fetch("/api/jungle", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, valeur }) });
      d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.erreur || "La jungle n'a pas répondu. Réessaie.");
      if (d.moi) { moi = d.moi; afficherCompte(); }
    }
    const j = d.jungle;
    JGL.recu = performance.now();
    JGL.infos = { ...JGL.infos, ...j };
    if (action === "rapide") { JGL.carte = null; dessinerJungle(); finRapide(j.rapide); return; }
    const nouvelle = action === "explorer";
    JGL.carte = j.carte;
    if (nouvelle) { dessinerJungle(); }
    else {
      const avantBouger = action === "fouiller" && JGL.carte.restants < 15;
      dessinerCarte(true, ancien);
      if (avantBouger && !JGL.carte.fini && !JGL.carte.chatiment) bruisser();
      majBandeauCharges();
    }
  } catch (e) { toast(e.message, true); }
  finally { JGL.occupe = false; }
}

function majBandeauCharges() {
  const i = JGL.infos, el = document.querySelector(".jgl-eclairs");
  if (el) el.querySelectorAll("i").forEach((x, k) => x.classList.toggle("plein", k < i.charges));
  const fini = !JGL.carte || JGL.carte.fini;
  if ($("jgl-explorer")) $("jgl-explorer").disabled = !fini || !i.charges;
  if ($("jgl-rapide")) $("jgl-rapide").disabled = !fini || !i.charges;
}

function bruisser() {   // les ganks se déplacent : tous les buissons cachés frémissent, sans dire lesquels
  if (calme()) return;
  document.querySelectorAll(".buisson").forEach((b, n) => {
    b.animate([{ transform: "translate(-50%,-50%)" }, { transform: "translate(calc(-50% - 3px),-50%) rotate(-3deg)" }, { transform: "translate(calc(-50% + 3px),-50%) rotate(3deg)" }, { transform: "translate(-50%,-50%)" }],
      { duration: 420, delay: 350 + (n % 5) * 40 });
  });
  document.querySelectorAll(".case .chiffre").forEach((c) => c.animate([{ filter: "brightness(1)" }, { filter: "brightness(2.2)" }, { filter: "brightness(1)" }], { duration: 600, delay: 700 }));
}

// ---------- les animations d'une fouille ----------
function jouerEvenement(ev, ancien) {
  if (ev.cle === "chatiment") return;
  const plateau = $("jgl-plateau"), cel = ev.case != null ? document.querySelector(`.case[data-k="${ev.case}"]`) : null;
  if (cel && !calme()) cel.animate([{ transform: "translate(-50%,-50%) scale(.3)", opacity: 0 }, { transform: "translate(-50%,-50%) scale(1.15)", opacity: 1 }, { transform: "translate(-50%,-50%) scale(1)" }], { duration: 420, easing: "cubic-bezier(.2,1.4,.4,1)" });
  if (cel) eclatsHerbe(cel);
  if (ev.cle === "gank") {
    plateau.classList.remove("secousse"); void plateau.offsetWidth; plateau.classList.add("secousse");
    flash("gank", "GANK !");
  } else if (ev.cle === "camp") {
    apparition(MONSTRE_IMG[ev.monstre] || "loup", ev.monstre, ev);
  } else if (ev.cle === "tresor") {
    flash("or", "Trésor !"); pluiePieces(cel);
  } else if (ev.cle === "fruit") {
    flash("miel", ev.efface ? "Un gank est effacé" : "Fruit de miel");
  } else if (ev.cle === "coffre") {
    flash("hextech", "Coffre hextech !");
  }
  if ((ev.cartes || []).length) setTimeout(() => montrerTrouvailles(ev.cartes), 900);
}
function eclatsHerbe(cel) {
  if (calme()) return;
  const p = $("jgl-plateau"), r = cel.getBoundingClientRect(), rp = p.getBoundingClientRect();
  for (let i = 0; i < 14; i++) {
    const f = document.createElement("i"); f.className = "brin-vole";
    f.style.left = `${r.left - rp.left + r.width / 2}px`; f.style.top = `${r.top - rp.top + r.height / 2}px`;
    p.appendChild(f);
    const a = Math.random() * 6.28, v = 40 + Math.random() * 70;
    f.animate([{ transform: "translate(0,0) rotate(0)", opacity: 1 }, { transform: `translate(${Math.cos(a) * v}px,${Math.sin(a) * v - 30}px) rotate(${Math.random() * 400}deg)`, opacity: 0 }],
      { duration: 700 + Math.random() * 300, easing: "cubic-bezier(.2,.7,.4,1)" }).onfinish = () => f.remove();
  }
}
function flash(genre, texte) {
  const f = $("jgl-flash"); if (!f) return;
  f.className = "jgl-flash " + genre; f.innerHTML = `<span>${esc(texte)}</span>`;
  void f.offsetWidth; f.classList.add("actif");
  setTimeout(() => f.classList.remove("actif"), 1100);
}
function apparition(img, nom, ev) {
  const p = $("jgl-plateau"); if (!p || calme()) return;
  const d = document.createElement("div"); d.className = "jgl-monstre";
  d.innerHTML = `<img src="${imgJgl(img)}" alt=""><b>${esc(nom)}</b><span>${ev.xp ? `✨ +${nombre(ev.xp)} XP` : ""}${ev.golds ? ` · 💰 +${nombre(ev.golds)}` : ""}</span><i class="entaille"></i>`;
  p.appendChild(d);
  setTimeout(() => d.remove(), 1500);
}
function pluiePieces(cel) {
  if (!cel || calme()) return;
  const p = $("jgl-plateau"), r = cel.getBoundingClientRect(), rp = p.getBoundingClientRect();
  for (let i = 0; i < 16; i++) {
    const c = document.createElement("i"); c.className = "piece-vole"; c.textContent = "🪙";
    c.style.left = `${r.left - rp.left + r.width / 2}px`; c.style.top = `${r.top - rp.top + r.height / 3}px`; p.appendChild(c);
    const a = -Math.PI / 2 + (Math.random() - 0.5) * 2, v = 60 + Math.random() * 60;
    c.animate([{ transform: "translate(0,0) scale(.6)", opacity: 1 }, { transform: `translate(${Math.cos(a) * v}px,${Math.sin(a) * v}px) scale(1)`, opacity: 1, offset: 0.5 }, { transform: `translate(${Math.cos(a) * v * 1.3}px,${Math.sin(a) * v + 80}px) scale(.8)`, opacity: 0 }],
      { duration: 1000 + Math.random() * 300 }).onfinish = () => c.remove();
  }
}
function montrerTrouvailles(cartes) {
  toast("🎁 Un pack traînait dans les buissons : " + cartes.map((c) => `${c.nom} (${c.rarete})`).join(", "));
}

// ---------- le Châtiment ----------
function lancerChatiment(ch) {
  const p = $("jgl-plateau"); if (!p) return;
  const art = ch.cle === "bleu" ? "sentinelle" : "roncier";
  const o = document.createElement("div"); o.className = "jgl-smite " + ch.cle; o.id = "jgl-smite";
  o.innerHTML = `<img class="smite-art" src="${imgJgl(art + "_art")}" alt="">
    <div class="smite-haut"><b>${esc(ch.nom)}</b><span>Châtiment quand sa vie passe dans la zone dorée</span></div>
    <div class="smite-barre"><i class="zone" style="width:${ch.fenetre}%"></i><i class="vie" id="smite-vie"></i><span id="smite-pct">100 %</span></div>
    <button class="smite-bouton" id="smite-bouton" aria-label="Lancer le Châtiment">⚡<span>Châtiment</span></button>
    <p class="smite-aide">Clique, touche l'écran ou appuie sur Espace</p>`;
  p.appendChild(o);
  const debut = (JGL.recu || performance.now()) - (ch.ecoule || 0) * 1000, total = ch.paliers.length * ch.rythme * 1000;
  JGL.smite = { fini: false };
  const vie = $("smite-vie"), pct = $("smite-pct");
  const tour = (t) => {
    if (!JGL.smite || JGL.smite.fini) return;
    const e = t - debut, idx = Math.min(ch.paliers.length - 1, Math.floor(e / (ch.rythme * 1000)));
    const k = Math.min(1, (e % (ch.rythme * 1000)) / 260);   // glisse rapide vers le palier suivant
    const avant = ch.paliers[Math.max(0, idx - 1)], cible = ch.paliers[idx], v = idx === 0 ? cible : avant + (cible - avant) * (1 - (1 - k) ** 3);
    vie.style.width = `${v}%`; pct.textContent = `${Math.round(cible)} %`;
    o.classList.toggle("dans-zone", cible <= ch.fenetre);
    if (e >= total) { frapper(false); return; }
    requestAnimationFrame(tour);
  };
  requestAnimationFrame(tour);
  const clic = (ev) => { ev.preventDefault(); frapper(true); };
  $("smite-bouton").addEventListener("click", clic);
  o.addEventListener("pointerdown", (ev) => { if (ev.target === o || ev.target.classList.contains("smite-art")) clic(ev); });
  JGL.smiteClavier = (ev) => { if (ev.code === "Space") clic(ev); };
  addEventListener("keydown", JGL.smiteClavier);
}
async function frapper(clic) {
  if (!JGL.smite || JGL.smite.fini) return;
  JGL.smite.fini = true;
  removeEventListener("keydown", JGL.smiteClavier);
  const o = $("jgl-smite");
  if (clic && o && !calme()) {
    o.insertAdjacentHTML("beforeend", `<svg class="eclair" viewBox="0 0 100 300" preserveAspectRatio="none" aria-hidden="true"><polyline points="55,0 40,70 62,95 35,170 58,190 45,300" /></svg>`);
    o.classList.add("frappe");
  }
  const attente = new Promise((r) => setTimeout(r, clic ? 450 : 50));
  JGL.occupe = false;
  await agir("chatiment", clic);
  await attente;
  const ev = JGL.carte && JGL.carte.evenement;
  if (o) {
    o.classList.add("resultat", ev && ev.reussi ? "reussi" : "rate");
    o.insertAdjacentHTML("beforeend", `<div class="smite-fin"><b>${ev && ev.reussi ? "Châtiment réussi !" : ev && ev.pris != null ? "Trop tôt…" : "Raté…"}</b>
      <span>${ev ? `✨ +${nombre(ev.xp)} XP · 💰 +${nombre(ev.golds)} golds` : ""}</span></div>`);
    setTimeout(() => { o.remove(); JGL.smite = null; }, 1600);
  } else JGL.smite = null;
}

// ---------- fins ----------
function finCarte(c) {
  const p = $("jgl-plateau"); if (!p || p.querySelector(".jgl-fin")) return;
  const titre = c.fini === "clear" ? "Clear complet !" : c.fini === "ganks" ? "Retour à la base" : "Butin en poche";
  const sous = c.fini === "clear" ? `Il ne restait que des ganks : +20 % de butin.` : c.fini === "ganks" ? `${c.vies_max} ganks : ton équipe a dû rentrer.` : "Ton équipe est rentrée à la base.";
  p.insertAdjacentHTML("beforeend", `<div class="jgl-fin ${c.fini}"><div><p class="ar-fin-titre">${titre}</p><p class="ar-fin-sous">${sous}</p>
    <ul class="ar-gains"><li>✨ <b>+${nombre(c.xp)}</b> XP par carte</li><li>${PIECE}<b>+${nombre(c.golds)}</b> golds</li></ul>
    <div class="ar-fin-actions">${JGL.infos.charges ? `<button class="bouton" id="jgl-encore"><i class="orne g"></i>Nouvelle carte<i class="orne d"></i></button>` : `<p class="nb">Plus de charge pour l'instant : la prochaine arrive dans ${JGL.infos.prochaine ? enMinutes(JGL.infos.prochaine) : "un moment"}.</p>`}
      <button class="bouton secondaire" id="jgl-fermer"><i class="orne g"></i>Fermer<i class="orne d"></i></button></div></div></div>`);
  if ($("jgl-encore")) $("jgl-encore").onclick = () => agir("explorer", JGL.mise);
  $("jgl-fermer").onclick = () => { JGL.carte = null; dessinerJungle(); };
}
function finRapide(r) {
  if (!r) return;
  $("jgl-zone").innerHTML = `<section class="panneau jgl-rapide-fin"><p class="ar-fin-titre">Clear rapide</p>
    <ul class="ar-gains"><li>✨ <b>+${nombre(r.xp)}</b> XP par carte</li><li>${PIECE}<b>+${nombre(r.golds)}</b> golds</li>
    ${r.montees.length ? `<li class="petit">⬆️ ${esc(r.montees.join(", "))}</li>` : ""}${(r.lignes || []).map((l) => `<li class="fort">⭐ ${esc(l)}</li>`).join("")}</ul>
    <p class="nb">${r.mise} charge${r.mise > 1 ? "s" : ""} dépensée${r.mise > 1 ? "s" : ""}. Explorer toi-même rapporte jusqu'au double.</p></section>`;
}

// ---------- la démo (sans serveur) : les mêmes règles, jouées dans la page ----------
const jungleDemo = (() => {
  let infos = null, carte = null, cases = [];
  const R = { CASES: [["camp", 6], ["bleu", 1], ["rouge", 1], ["tresor", 2], ["gank", 3], ["fruit", 1]], VIES: 2, CLEAR: 20, CAMP: 1, GROS: [2.5, 1], TRESOR: 1.5,
    SMITE: { bleu: [[100, 72, 44, 66, 38, 14], 1.5], rouge: [[100, 92, 84, 76, 30, 10], 1.3] }, FENETRE: 35, BUTIN: 5 };
  const melange = (t) => { for (let i = t.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [t[i], t[j]] = [t[j], t[i]]; } return t; };
  const vois = (k) => { const x = k % 4, y = Math.floor(k / 4), r = []; for (let yy = y - 1; yy <= y + 1; yy++) for (let xx = x - 1; xx <= x + 1; xx++) if (xx >= 0 && xx < 4 && yy >= 0 && yy < 4 && (xx !== x || yy !== y)) r.push(yy * 4 + xx); return r; };
  const autour = (k) => vois(k).filter((v) => cases[v] === "gank" && !carte.vues.includes(v)).length;
  function etat() {
    if (!infos) infos = { charges: 9, max: 12, prochaine: 8020, mise_max: 4, mise_limite: 4, chasses: 327, bonus: 10, clear_xp: 15180, clear_golds: 2772, rapide_pct: 50, requis: 2, niveau: moi.niveau, unite_xp: 230, unite_golds: 33 };
    return { ...infos, carte: carte && !carte.fini ? pub() : null };
  }
  function pub() {
    return { ...carte, cote: 4, vies_max: R.VIES, restants: 16 - carte.vues.length, journal: carte.journal.slice(-6),
      cases: cases.map((c, k) => (carte.vues.includes(k) ? { vu: true, cle: c, n: autour(k), monstre: carte.monstres[k] } : { vu: false, repere: false })) };
  }
  const verser = (cx, cg) => { const xp = Math.round(infos.unite_xp * cx * 1.1), g = Math.round(infos.unite_golds * cg * 1.1); carte.xp += xp; carte.golds += g; carte.cx += xp; carte.cg += g; moi.golds += g; return [xp, g]; };
  function suite() {
    const caches = cases.map((c, k) => k).filter((k) => !carte.vues.includes(k));
    if (carte.vies <= 0) { carte.fini = "ganks"; carte.journal.push(`💀 ${R.VIES} ganks : ton équipe rentre à la base. Le butin ramassé est gardé.`); }
    else if (caches.every((k) => cases[k] === "gank")) { const [x, g] = verser(0, 0); carte.xp += Math.round(carte.cx * 0.2); carte.golds += Math.round(carte.cg * 0.2); carte.fini = "clear"; carte.journal.push("🏆 Clear complet ! +20 % du butin de la carte."); }
    else if (carte.vues.length >= 2) {
      for (const k of melange(cases.map((c, i) => i).filter((i) => cases[i] === "gank" && !carte.vues.includes(i)))) {
        const libres = vois(k).filter((v) => !carte.vues.includes(v) && cases[v] !== "gank");
        if (libres.length) { const v = libres[Math.floor(Math.random() * libres.length)]; [cases[k], cases[v]] = [cases[v], cases[k]]; }
      }
    }
  }
  function agir(action, valeur) {
    etat();
    if (action === "explorer" || action === "rapide") {
      if (!infos.charges) throw new Error("Tu n'as plus de charge de Châtiment.");
      const mise = Math.max(1, Math.min(Number(valeur) || 1, infos.charges, 4));
      infos.charges -= mise; infos.mise_max = Math.max(1, Math.min(infos.charges, 4));
      if (action === "rapide") { const xp = Math.round(infos.clear_xp * mise * 0.55), g = Math.round(infos.clear_golds * mise * 0.55); moi.golds += g; return { ...etat(), rapide: { xp, golds: g, mise, montees: [], lignes: [] } }; }
      cases = melange(R.CASES.flatMap(([c, n]) => Array(n).fill(c)).concat(Array(2).fill("vide")));
      carte = { mise, mult: R.BUTIN * mise, vues: [], vies: R.VIES, xp: 0, golds: 0, cx: 0, cg: 0, fini: false, bonus: 10, journal: ["Choisis un buisson à fouiller."], evenement: null, chatiment: null, monstres: {} };
      return etat();
    }
    if (!carte) throw new Error("Pas de carte en cours.");
    if (action === "fouiller") {
      const k = Number(valeur);
      if (carte.fini || carte.chatiment || carte.vues.includes(k)) return { ...etat(), carte: pub() };
      if (!carte.vues.length && cases[k] === "gank") { const autres = cases.map((c, i) => i).filter((i) => cases[i] !== "gank"); const v = autres[Math.floor(Math.random() * autres.length)]; [cases[k], cases[v]] = [cases[v], cases[k]]; }
      const cle = cases[k]; carte.vues.push(k);
      const ev = { case: k, cle, xp: 0, golds: 0, cartes: [], lignes: [] };
      if (cle === "camp") { ev.monstre = ["Gromp", "Loup des ténèbres", "Corbin écarlate", "Golem ancien"][Math.floor(Math.random() * 4)]; carte.monstres[k] = ev.monstre; [ev.xp, ev.golds] = verser(R.CAMP * carte.mult, R.CAMP * carte.mult); carte.journal.push(`${({ "Gromp": "🐸", "Loup des ténèbres": "🐺", "Corbin écarlate": "🐦", "Golem ancien": "🪨" })[ev.monstre]} ${ev.monstre} : camp nettoyé. ✨ +${ev.xp} XP par carte · 💰 +${ev.golds} golds`); }
      else if (cle === "tresor") { [, ev.golds] = verser(0, R.TRESOR * carte.mult); carte.journal.push(`💰 Un trésor oublié ! 💰 +${ev.golds} golds`); }
      else if (cle === "gank") { carte.vies--; carte.journal.push("⚔️ Gank ! Un jungler ennemi t'attendait." + (carte.vies ? ` Encore ${carte.vies} et ton équipe rentre à la base.` : "")); }
      else if (cle === "fruit") { ev.efface = carte.vies < R.VIES; carte.vies = Math.min(R.VIES, carte.vies + 1); carte.journal.push("🍯 Fruit de miel : " + (ev.efface ? "un gank est effacé." : "aucun gank à effacer.")); }
      else if (cle === "vide") carte.journal.push("🍃 Rien dans ce buisson.");
      if (cle === "bleu" || cle === "rouge") { const [pal, ry] = R.SMITE[cle]; carte.chatiment = { cle, nom: cle === "bleu" ? "Sentinelle bleue" : "Roncier rouge", paliers: pal, rythme: ry, fenetre: R.FENETRE, ecoule: 0, debut: performance.now() }; }
      else suite();
      carte.evenement = ev;
    } else if (action === "chatiment") {
      const a = carte.chatiment; if (!a) return { ...etat(), carte: pub() };
      const brut = (performance.now() - a.debut) / 1000;
      const idx = [brut, brut - 0.35].map((e) => Math.floor(Math.max(0, e) / a.rythme)).filter((i) => i < a.paliers.length);
      const bon = idx.find((i) => a.paliers[i] <= R.FENETRE);
      const pris = valeur && idx.length ? a.paliers[bon != null ? bon : idx[idx.length - 1]] : null, reussi = pris != null && pris <= R.FENETRE;
      const part = (reussi ? R.GROS[0] : R.GROS[1]) * carte.mult, [xp, golds] = verser(part, part);
      carte.journal.push(reussi ? `⚡ Châtiment réussi sur ${a.nom} (à ${pris} % de PV) ! ✨ +${xp} XP · 💰 +${golds} golds` : `${a.nom} : ${pris != null ? `Châtiment trop tôt (à ${pris} %)` : "vaincu sans Châtiment"}, petit butin. ✨ +${xp} XP · 💰 +${golds} golds`);
      carte.evenement = { case: null, cle: "chatiment", monstre: a.nom, reussi, pris, xp, golds, cartes: [], lignes: [] };
      carte.chatiment = null; suite();
    } else if (action === "rentrer") { carte.fini = "base"; carte.journal.push("🏠 Ton équipe rentre à la base, butin en poche."); carte.evenement = null; }
    const res = { ...etat(), carte: pub() };
    if (carte.fini) carte = null;
    return res;
  }
  return { etat, agir };
})();
