// 2Hot4Deck · le site (version test) : accueil, cartes, classement, profils, et ta collection (connexion Discord).
// Tout est en lecture seule : le site n'envoie jamais rien qui modifie le jeu.
const $ = (id) => document.getElementById(id);
const RARETES = ["LR", "UR", "SSR", "SR", "R", "N"];
const RANG = { LR: 0, UR: 1, SSR: 2, SR: 3, R: 4, N: 5 };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const nombre = (n) => (n ?? 0).toLocaleString("fr-FR");
const PIECE = `<i class="piece" aria-hidden="true"></i>`;   // l'icône des golds (celle du jeu)
const etoiles = (n) => (n ? "★".repeat(n) : "");
const MODES = { worlds: "Worlds", pvp: "PvP", boss: "Boss de la tour" };
const DISCORD = `<svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><path d="M20.3 4.4A19.6 19.6 0 0 0 15.4 3l-.6 1.2a18 18 0 0 0-5.6 0L8.6 3a19.5 19.5 0 0 0-4.9 1.5C.6 9.1-.3 13.6.1 18.1a19.8 19.8 0 0 0 6 3l1.3-2a12.7 12.7 0 0 1-2-1l.5-.4a14 14 0 0 0 12.2 0l.5.4c-.6.4-1.3.7-2 1l1.3 2a19.7 19.7 0 0 0 6-3c.5-5.2-.8-9.7-3.6-13.7ZM8 15.4c-1.2 0-2.2-1.1-2.2-2.4S6.8 10.6 8 10.6s2.2 1.1 2.2 2.4-1 2.4-2.2 2.4Zm8 0c-1.2 0-2.2-1.1-2.2-2.4s1-2.4 2.2-2.4 2.2 1.1 2.2 2.4-1 2.4-2.2 2.4Z"/></svg>`;

async function api(chemin) {
  const r = await fetch(chemin);
  let d = null;
  try { d = await r.json(); } catch (e) {}
  return { ok: r.ok, statut: r.status, d };
}

// ---------- vignettes et fiche d'une carte (partagées par toutes les pages) ----------
// la carte en 3D (cartes3d.js) : elle s'incline vers la souris ; reflet holographique pour les SSR, UR et LR
// Certaines cartes existent en 3 couches (décor, personnage, cadre) : le personnage bouge dans la fenêtre du cadre.
const COUCHES_3D = new Set([]);   // essai des cartes en couches : désactivé pour l'instant
const absolu = (u) => new URL(u, location.href).href;
const couche = (id, k) => `/static/3d/${id}_${k}.webp`;
const carte3d = (c, img) => {
  const reflets = `<i class="holo" aria-hidden="true"></i><i class="eclat" aria-hidden="true"></i>`;
  if (!COUCHES_3D.has(c.id)) return `<span class="c3d" data-rar="${c.rarete}" style="--img:url('${esc(absolu(c.image))}')">${img}${reflets}</span>`;
  const fen = absolu(couche(c.id, "fen").replace(".webp", ".png"));
  return `<span class="c3d couches" data-rar="${c.rarete}" style="--img:url('${esc(absolu(c.image))}')">
    <span class="c-art" style="-webkit-mask-image:url('${esc(fen)}');mask-image:url('${esc(fen)}')"><img class="c-fond" src="${couche(c.id, "fond")}" alt="" loading="lazy"><img class="c-perso" src="${couche(c.id, "perso")}" alt="" loading="lazy"></span>
    <img class="c-cadre" src="${couche(c.id, "cadre")}" alt="${esc(c.nom)}" loading="lazy">${reflets}</span>`;
};
function vignette(c, extra = "") {
  return `<button class="carte" data-id="${esc(c.id)}" style="--c:var(--${c.rarete})" aria-label="${esc(c.nom)}, ${c.rarete}">
    ${c.image ? carte3d(c, `<img loading="lazy" src="${esc(c.image)}" alt="">`) : `<div class="vide">${esc(c.nom)}</div>`}
    <div class="marques">${extra}</div>
    <div class="nom">${esc(c.nom)}</div>
    <div class="info"><span class="rar">${c.rarete}</span> · niv. ${c.niveau}${c.etoiles ? " · " + etoiles(c.etoiles) : ""}</div>
  </button>`;
}

// icône officielle de l'item ou de la rune si on l'a, sinon l'emoji du bot
const ico = (x, cls = "ico") => x && x.icone ? `<img class="${cls}" src="${esc(x.icone)}" alt="" loading="lazy">` : (x && x.emoji) || "";
const bloc = (titre, texte, vide) => `<div class="bloc"><h3>${titre}</h3>${texte ? `<p>${texte}</p>` : `<p class="rien">${vide}</p>`}</div>`;

function blocTier(t) {
  if (!t) return "";
  const ligne = (m) => t[m] ? `<tr><th>${MODES[m]}</th><td><b class="tier t-${t[m].tier}">${t[m].tier}</b></td><td>${t[m].rang}<sup>e</sup></td>
    <td>${ico({ icone: t[m].item_icone })} ${esc(t[m].item)}${t[m].rune ? ` · ${ico({ icone: t[m].rune_icone })} ${esc(t[m].rune)}` : ""}</td></tr>` : "";
  return `<div class="bloc"><h3>Tier list · meilleur équipement</h3><table class="mini"><tbody>${ligne("worlds")}${ligne("pvp")}${ligne("boss")}</tbody></table>
    <p class="note">Aux Worlds, les runes ne comptent pas : seul l'item compte.</p></div>`;
}

function ouvrirFiche(c, perso) {
  const d = $("detail");
  d.style.setProperty("--c", `var(--${c.rarete})`);
  d.dataset.id = c.id;
  const eveil = c.eveil && !`${c.passif} ${c.actif}`.includes(c.eveil);
  $("d-contenu").innerHTML = `<div class="d-grille">
    <div class="d-visuel">${c.image ? carte3d(c, `<img src="${esc(c.image)}" alt="${esc(c.nom)}">`) : `<div class="vide" style="aspect-ratio:500/846">${esc(c.nom)}</div>`}</div>
    <div>
      <h2 id="d-nom">${esc(c.nom)}</h2>
      <p class="sous"><span class="rar" style="--c:var(--${c.rarete})">${c.rarete}</span> · ${esc(c.role)} · ${esc(c.region)}${c.tier?.src ? ` · ${esc(c.tier.src)}` : ""}${perso && c.equipe ? " · 🛡️ dans ton équipe" : ""}</p>
      <div class="chiffres-carte">
        <div><b>${c.niveau}</b><span>niveau${c.etoiles ? " · " + etoiles(c.etoiles) : ""}${perso ? "" : " (max)"}</span></div>
        <div><b>${nombre(c.pv)}</b><span>PV</span></div>
        <div><b>${nombre(c.atk)}</b><span>attaque</span></div>
      </div>
      ${perso ? actionsCarte(c) : ""}
      ${bloc("Passif", esc(c.passif), "Pas de passif.")}
      ${bloc(c.ulti ? `Actif · ${esc(c.ulti)}` : "Actif", esc(c.actif), "Pas d'actif.")}
      ${eveil ? bloc("Éveil UR", esc(c.eveil)) : ""}
      ${perso && c.item ? bloc("Effet de ton item", `${ico(c.item)} <b>${esc(c.item.nom)}</b> niv. ${c.item.niveau} · ${esc(c.item.effet)}`) : ""}
      ${perso && c.rune ? bloc("Effet de ta rune", `${ico(c.rune)} <b>${esc(c.rune.nom)}</b> · ${esc(c.rune.effet)}`) : ""}
      ${blocTier(c.tier)}
      ${!perso && c.possedee_par != null ? `<p class="note">${c.possedee_par ? `${c.possedee_par} joueur${c.possedee_par > 1 ? "s l'ont" : " l'a"} sur le serveur.` : "Personne ne l'a encore sur le serveur."}</p>` : ""}
    </div></div>`;
  if (!d.open) d.showModal();
}

function brancherGrille(grille, source, perso) {
  grille.addEventListener("click", (e) => {
    const b = e.target.closest(".carte");
    if (!b) return;
    const c = source().find((x) => x.id === b.dataset.id);
    if (c) ouvrirFiche(c, perso);
  });
}

function puces(conteneur, options, actif, auChoix) {
  conteneur.innerHTML = options.map(([v, t, c]) => `<button class="puce" data-r="${v}" style="--c:${c}" aria-pressed="${v === actif}">${t}</button>`).join("");
  conteneur.onclick = (e) => {
    const b = e.target.closest("button"); if (!b) return;
    conteneur.querySelectorAll("button").forEach((x) => x.setAttribute("aria-pressed", x === b));
    auChoix(b.dataset.r);
  };
}

const rangMode = (c, m) => c.tier?.[m]?.rang ?? 999;
const puissance = (c) => (c.pv || 0) / 5 + (c.atk || 0) * 2;

// ---------- connexion ----------
let moi = null;   // la collection du joueur connecté, ou null
function boutonConnexion(texte = "Se connecter avec Discord", classe = "bouton") {
  return `<a class="${classe}" href="/connexion">${DISCORD}${texte}</a>`;
}
function afficherCompte() {
  setTimeout(() => chatPret(), 0);
  if (moi) {
    $("compte").innerHTML = `<span class="monnaie" title="Golds">${PIECE}${nombre(moi.golds)}</span>
      ${moi.avatar ? `<img src="${esc(moi.avatar)}" alt="">` : ""}
      <span class="qui-compte"><b>${esc(moi.pseudo)}</b><span>Niveau ${moi.niveau}</span></span>
      <a class="bouton discret" href="/deconnexion">Quitter</a>`;
    $("hero-actions").innerHTML = `<a class="bouton" href="#collection"><i class="orne g"></i>Voir ma collection<i class="orne d"></i></a><a class="bouton secondaire" href="#cartes"><i class="orne g"></i>Toutes les cartes<i class="orne d"></i></a>`;
  } else {
    $("compte").innerHTML = boutonConnexion("Connexion", "bouton discord discret");
    $("hero-actions").innerHTML = `${boutonConnexion()}<a class="bouton secondaire" href="#cartes"><i class="orne g"></i>Voir les cartes<i class="orne d"></i></a>`;
  }
  remplirPacks();
}
async function verifierConnexion() {
  const r = await api("/api/moi").catch(() => ({ ok: false }));
  moi = r.ok ? r.d : null;
  afficherCompte();
}

// ---------- accueil ----------
const PACKS = [["gratuit", "gratuit", "Pack gratuit", "/static/pack_gratuit.webp"], ["normal", "normal", "Pack normal", "/static/pack_normal.webp"],
  ["pro", "pro", "Pack Worlds", "/static/pack_worlds.webp"], ["ur", "ur", "Pack UR", "/static/pack_ur.webp"],
  ["lec", "lec", "Pack LEC", "/static/pack_lec.webp"], ["niveau", "niv", "Pack niveau", "/static/pack_niveau.webp"]];
const PRIX_PACK = 100;   // prix d'un pack normal à la boutique du bot (data.PRIX_PACK)
function attenteGratuit(s) {
  if (s <= 0) return "Disponible !";
  const h = Math.floor(s / 3600), m = Math.ceil((s % 3600) / 60);
  return h ? `dans ${h} h ${String(m).padStart(2, "0")}` : `dans ${m} min`;
}
const prix = (k) => (moi && moi.prix && moi.prix[k]) || { normal: 100, normal10: 900, mega: 4000, mega_cartes: 50 }[k];
const BASE_PACK = (cle) => (cle === "normal10" || cle === "mega" ? "normal" : cle.replace(/5$/, ""));
function peutOuvrir(cle) {
  if (!moi) return false;
  if (cle === "normal" || cle === "normal10" || cle === "mega") return moi.golds >= prix(cle);
  if (cle === "gratuit") return (moi.gratuit_dans ?? 0) <= 0;
  return (moi.packs[BASE_PACK(cle)] ?? 0) > 0;
}
function remplirPacks() {
  $("packs").innerHTML = PACKS.map(([cle, classe, nom, image]) => {
    const qte = cle === "normal" ? `${nombre(prix("normal"))} golds` : !moi ? "sur Discord" : cle === "gratuit" ? attenteGratuit(moi.gratuit_dans ?? 0) : `${nombre(moi.packs[cle] ?? 0)} à ouvrir`;
    const pret = peutOuvrir(cle);
    const dedans = `<img class="pack-img" src="${image}" alt=""><span class="nom-pack">${nom.replace("Pack ", "")}</span><span class="qte">${cle === "normal" ? PIECE + nombre(prix("normal")) : qte}</span>`;
    return moi ? `<button type="button" class="pack ${classe}${pret ? " pret" : " epuise"}" data-pack="${cle}" aria-label="Ouvrir un ${esc(nom.toLowerCase())} (${esc(qte)})">${dedans}</button>`
               : `<div class="pack ${classe}">${dedans}</div>`;
  }).join("");
  const note = moi ? "Clique sur un pack pour l'ouvrir. Tes cartes arrivent aussi dans ta collection sur Discord." : "Connecte-toi pour ouvrir tes packs ici, ou ouvre-les sur le serveur Discord.";
  if ($("packs-note")) $("packs-note").textContent = note;
  else $("packs").insertAdjacentHTML("afterend", `<p class="packs-note" id="packs-note">${note}</p>`);
}

// ---------- ouverture des packs ----------
// C'est le bot qui ouvre le pack (mêmes taux et mêmes garanties que sur Discord) ; ici, on ne fait que la mise en scène.
const COULEUR_RARETE = { N: "#8f9bb3", R: "#4f9be8", SR: "#a66bf0", SSR: "#f0a23a", UR: "#f0506e", LR: "#ff3b3b" };
const pause = (ms) => new Promise((r) => setTimeout(r, ms));
const calme = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
let ouvertureEnCours = false;

async function demanderPack(cle) {
  if (ENDEMO) {   // la démo tire au hasard parmi les cartes du jeu : on les charge si besoin
    if (!catalogue) { const r = await api("/api/cartes").catch(() => ({ ok: false })); if (r.ok) catalogue = r.d; }
    return simulerPack(cle);
  }
  const r = await fetch("/api/ouvrir", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pack: cle }) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.erreur || "Le pack n'a pas pu s'ouvrir.");
  return d;
}

function carteTiree(c, k, petit) {
  // une carte encadrée garde ses proportions ; une simple illustration (sbires, monstres) remplit le cadre
  const recto = c.image ? `<img src="${esc(c.image)}" alt=""${c.encadree === false ? ' class="brute"' : ""}>` : `<div class="vide">${esc(c.nom)}</div>`;
  const info = petit
    ? `<div class="ouv-info"><span class="rar">${c.rarete}</span>${c.nouvelle ? `<span class="nouv">Nouvelle</span>` : ""}</div>`
    : `<div class="ouv-info"><span class="rar">${c.rarete}</span>${c.nouvelle ? `<span class="nouv">Nouvelle !</span>` : ""}
      <b>${esc(c.nom)}</b><span class="statut">${esc(c.nouvelle ? "Ajoutée à ta collection" : c.statut || "")}</span>
      ${(c.en_plus || []).map((x) => `<span class="statut or">${esc(x.replace(/\*\*/g, ""))}</span>`).join("")}</div>`;
  return `<div class="ouv-carte" style="--c:var(--${c.rarete});--k:${k}" title="${esc(c.nom + (c.statut ? " · " + c.statut : ""))}">
    <div class="ouv-tourne"><div class="face dos"><img src="/static/dos_carte.webp" alt=""></div><div class="face recto">${recto}</div></div>${info}</div>`;
}
function coachTire(c, k, petit) {
  const recto = c.image ? `<img src="${esc(c.image)}" alt="">` : `<div class="vide">${esc(c.pseudo)}</div>`;
  const info = petit
    ? `<div class="ouv-info"><span class="rar">Coach</span>${c.nouveau ? `<span class="nouv">Nouveau</span>` : ""}</div>`
    : `<div class="ouv-info"><span class="rar">Coach</span>${c.nouveau ? `<span class="nouv">Nouveau !</span>` : ""}
      <b>${esc(c.pseudo)}</b><span class="statut">${esc(c.poste)} · ${esc(c.equipe)}</span><span class="statut">${esc(c.bonus)}</span>
      ${c.equipe_auto ? `<span class="statut or">Équipé comme coach.</span>` : ""}</div>`;
  return `<div class="ouv-carte coach" style="--c:var(--or);--k:${k}" title="${esc(c.pseudo + " · " + c.poste + " · " + c.equipe)}">
    <div class="ouv-tourne"><div class="face dos"><img src="/static/dos_carte.webp" alt=""></div><div class="face recto">${recto}</div></div>${info}</div>`;
}
const NOM_OUVERTURE = { normal10: "10 packs", mega: "Méga tirage", niveau5: "5 packs de niveau", ur5: "5 packs UR", pro5: "5 packs Worlds", lec5: "5 packs LEC" };

async function ouvrirPack(cle) {
  if (!moi || ouvertureEnCours) return;
  const def = PACKS.find((x) => x[0] === BASE_PACK(cle));
  if (!def) return;
  const titre = NOM_OUVERTURE[cle] || def[2];
  if (!peutOuvrir(cle)) {
    toast(["normal", "normal10", "mega"].includes(cle) ? `Il te faut ${nombre(prix(cle))} golds pour ça.` : cle === "gratuit" ? `Prochain pack gratuit ${attenteGratuit(moi.gratuit_dans)}.` : `Tu n'as pas de ${def[2].toLowerCase()} à ouvrir.`, true);
    return;
  }
  ouvertureEnCours = true;
  const d = $("ouverture"), scene = $("ouv-scene");
  scene.className = "ouv-scene";
  scene.style.removeProperty("--lueur");
  const plusieurs = cle !== BASE_PACK(cle);
  scene.innerHTML = `<div class="ouv-pack${plusieurs ? " pile" : ""}"><img src="${def[3]}" alt="">${plusieurs ? `<img src="${def[3]}" alt=""><img src="${def[3]}" alt="">` : ""}</div>
    <p class="ouv-texte">${esc(plusieurs ? titre + " s'ouvrent…" : "Le " + def[2].toLowerCase() + " s'ouvre…")}</p>`;
  $("ouv-actions").innerHTML = "";
  if (!d.open) d.showModal();
  const minimum = pause(calme() ? 250 : 1500);
  let res = null, erreur = null;
  try { res = await demanderPack(cle); } catch (e) { erreur = e; }
  await minimum;
  if (erreur) {
    scene.className = "ouv-scene";
    scene.innerHTML = `<p class="ouv-erreur">${esc(erreur.message)}</p>`;
    $("ouv-actions").innerHTML = `<button class="bouton secondaire" data-ouv="fermer"><i class="orne g"></i>Fermer<i class="orne d"></i></button>`;
    ouvertureEnCours = false;
    return;
  }
  const t = res.tirage || { cartes: [] };
  delete res.tirage;
  moi = res;
  const coachs = t.coachs || [];
  const meilleure = t.cartes.reduce((m, c) => (RANG[c.rarete] < RANG[m] ? c.rarete : m), "N");
  scene.style.setProperty("--lueur", coachs.length && RANG[meilleure] > RANG.UR ? "var(--or)" : COULEUR_RARETE[meilleure]);
  scene.classList.add("eclat", "r-" + meilleure);
  await pause(calme() ? 0 : 750);
  const n = coachs.length + t.cartes.length, petit = n > 3;
  const pas = n > 20 ? 0.04 : n > 3 ? 0.12 : 0.35;   // plus il y a de cartes, plus elles se retournent vite
  const pieces = coachs.map((c, k) => coachTire(c, k * pas / 0.35, petit)).concat(t.cartes.map((c, k) => carteTiree(c, (k + coachs.length) * pas / 0.35, petit)));
  let resume = "";
  if (petit) {
    const compte = {};
    t.cartes.forEach((c) => (compte[c.rarete] = (compte[c.rarete] || 0) + 1));
    const nouvelles = t.cartes.filter((c) => c.nouvelle).length;
    resume = `<p class="ouv-resume">${RARETES.filter((r) => compte[r]).map((r) => `<span style="color:var(--${r})"><b>${compte[r]}</b> ${r}</span>`).join("")}`
      + (coachs.length ? `<span style="color:var(--or-clair)"><b>${coachs.length}</b> coach${coachs.length > 1 ? "s" : ""}</span>` : "")
      + `<span><b>${nouvelles}</b> nouvelle${nouvelles > 1 ? "s" : ""}</span></p>`;
  }
  const titreFin = t.ouverts && cle.endsWith("5") ? `${t.ouverts} ${t.ouverts > 1 ? def[2].replace("Pack", "packs") : def[2].toLowerCase()}` : titre;
  scene.innerHTML = `<p class="ouv-titre">${esc(titreFin)}</p>${resume}${t.message ? `<p class="ouv-message">${esc(t.message)}</p>` : ""}
    <div class="ouv-cartes n${Math.min(n, 6)}${petit ? " multi" : ""}${n > 20 ? " beaucoup" : ""}">${pieces.join("")}</div>`;
  requestAnimationFrame(() => requestAnimationFrame(() => scene.classList.add("revele")));
  const encore = peutOuvrir(cle);
  $("ouv-actions").innerHTML = (encore ? `<button class="bouton" data-ouv="encore" data-pack="${cle}"><i class="orne g"></i>${plusieurs ? "Encore" : "Encore un"}<i class="orne d"></i></button>` : "")
    + `<button class="bouton secondaire" data-ouv="fermer"><i class="orne g"></i>${encore ? "Fermer" : "Terminé"}<i class="orne d"></i></button>`;
  afficherCompte();
  if (!$("v-collection").hidden) { afficherSousVue(); }
  if (!$("v-packs").hidden) pagePacks();
  ouvertureEnCours = false;
}

// ---------- la tour ----------
// Le combat est calculé par le moteur du bot ; le site le rejoue action par action (qui agit, ce qui se passe, les PV de chacun).
let tourDonnees = null;
async function pageTour() {
  const box = $("t-contenu");
  if (!moi) {
    box.innerHTML = `<div class="message">Connecte-toi avec Discord pour monter la tour ici.<div class="actions">${boutonConnexion()}</div></div>`;
    return;
  }
  if (!tourDonnees) {
    box.innerHTML = `<p class="nb">Chargement…</p>`;
    const r = await api("/api/tour").catch(() => ({ ok: false }));
    if (!r.ok) { box.innerHTML = `<p class="nb">${esc(r.d?.erreur || "La tour n'est pas disponible pour l'instant.")}</p>`; return; }
    tourDonnees = r.d;
  }
  const t = tourDonnees, pct = Math.round((t.etage / t.max) * 100);
  const equipe = (t.equipe || moi.equipe).map((id) => carteDe(id)).filter(Boolean);
  box.innerHTML = `<div class="tour-grille">
    <section class="panneau tour-etage">
      <div class="tour-progres"><span>Étage <b>${t.etage}</b> / ${t.max}</span><div class="barre"><i style="width:${pct}%"></i></div></div>
      <p class="tour-sur">${t.boss ? "Boss" : "Prochain étage"}</p>
      <h2 class="tour-num">Étage ${t.prochain}</h2>
      <div class="tour-adv${t.boss ? " boss" : ""}">${t.adversaires.map((a) => `<figure>${a.image ? `<img src="${esc(a.image)}" alt="">` : `<div class="vide">${esc(a.nom)}</div>`}
        <figcaption><b>${esc(a.nom)}</b><span>${nombre(a.pv)} PV</span></figcaption></figure>`).join("")}</div>
      ${t.prochain > 100 ? `<p class="tour-note">Tour difficile : les soins sont réduits.</p>` : ""}
      ${t.fini ? `<p class="tour-note">Tu as vaincu tous les étages de la tour.</p>` : `<button class="bouton grand" id="t-combattre"><i class="orne g"></i>Combattre<i class="orne d"></i></button>`}
    </section>
    <section class="panneau tour-equipe">
      <div class="panneau-tete"><h2>Ton équipe</h2><a href="#collection" data-equipe>Changer →</a></div>
      <div class="tour-cartes">${equipe.map((c, k) => vignette(c, k === 0 ? `<span class="tag-leader">Leader</span>` : "")).join("")}</div>
      <p class="tour-note">C'est la même équipe que sur Discord, avec ses items et ses runes.</p>
    </section>
  </div>`;
  if ($("t-combattre")) $("t-combattre").onclick = () => combattreTour();
  box.querySelector("[data-equipe]").onclick = () => { sousVue = "equip"; };
}

async function combattreTour(etage) {
  let c;
  if (ENDEMO) c = tourDonnees.combats[String(etage || tourDonnees.prochain)];
  else {
    const r = await fetch("/api/tour", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { toast(d.erreur || "Le combat n'a pas pu se lancer.", true); return; }
    c = d.combat; if (d.moi) { moi = d.moi; afficherCompte(); } tourDonnees = null;
  }
  if (c) jouerCombat(c);
}

let arVitesse = 1, arFinir = null;
const PV_TXT = (n) => (n >= 10000 ? (n / 1000).toFixed(n >= 100000 ? 0 : 1).replace(".", ",") + " k" : nombre(n));
// l'item et la rune portés par nos cartes, en petites icônes sur la carte (comme sur la maquette)
function equipementArene(u) {
  if (u.camp !== 0 || !moi) return "";
  const c = carteDe(u.cid); if (!c) return "";
  const pieces = [c.item && [c.item, "Item"], c.rune && [c.rune, "Rune"]].filter(Boolean);
  if (!pieces.length) return "";
  return `<div class="ar-equip">${pieces.map(([x, genre]) => x.icone
    ? `<img src="${esc(x.icone)}" alt="${esc(genre + " : " + x.nom)}" title="${esc(x.nom)}">`
    : `<span title="${esc(x.nom)}">${x.emoji || ""}</span>`).join("")}</div>`;
}
function uniteHtml(u, k) {
  const img = u.image ? `<img src="${esc(u.image)}" alt="">` : `<div class="vide">${esc(u.nom)}</div>`;
  const pips = u.cout ? `<div class="ar-jauge" title="Ulti">${Array.from({ length: u.cout }, () => "<i></i>").join("")}</div>` : "";
  return `<div class="ar-unite${u.boss ? " boss" : ""}" id="ar-u${k}" style="--c:var(--${u.rarete || "UR"})">
    <div class="ar-carte">${u.boss ? `<img class="ar-cadre-boss" src="/static/cadre_boss.webp" alt="">` : ""}${img}${equipementArene(u)}<div class="ar-chiffres"></div></div>
    <div class="ar-nom">${esc(u.nom.replace(" adverse", ""))}</div>
    <div class="ar-pv"><div class="piste"><i class="rempli"></i><i class="bouclier"></i></div><span></span></div>${pips}</div>`;
}
function majUnite(k, u, e, anime) {
  const el = $("ar-u" + k); if (!el) return;
  const [pv, bouclier, jauge, cout] = e;
  const avant = Number(el.dataset.pv ?? u.pv);
  el.querySelector(".rempli").style.width = `${Math.max(0, Math.min(100, (pv / u.pvmax) * 100))}%`;
  el.querySelector(".bouclier").style.width = `${Math.min(100, (bouclier / u.pvmax) * 100)}%`;
  el.querySelector(".ar-pv span").textContent = `${PV_TXT(pv)} / ${PV_TXT(u.pvmax)}`;
  el.querySelectorAll(".ar-jauge i").forEach((p, i) => p.classList.toggle("plein", i < Math.min(jauge, cout)));
  el.dataset.pv = pv;
  el.classList.toggle("ko", pv <= 0);
  if (anime && pv !== avant) {
    const n = document.createElement("span");
    n.className = "ar-nombre " + (pv < avant ? "degat" : "soin");
    n.textContent = (pv < avant ? "-" : "+") + nombre(Math.abs(avant - pv));
    el.querySelector(".ar-chiffres").appendChild(n);
    setTimeout(() => n.remove(), 1400);
    if (pv < avant) { el.classList.remove("touche"); void el.offsetWidth; el.classList.add("touche"); }
  }
}
function ligneFil(l) {
  const li = document.createElement("li");
  if (/^✨/u.test(l)) li.className = "ulti moi"; else if (/^🔥/u.test(l)) li.className = "ulti eux"; else if (/K\.O\./.test(l)) li.className = "ko";
  // les chiffres et le nom de l'ulti ressortent, comme sur la maquette
  li.innerHTML = esc(l)
    .replace(/(lance )(.+?)( sur | :|,|$)/, '$1<b class="nom-ulti">$2</b>$3')
    .replace(/(\d[\d\s]*\d|\d)( dégâts| PV| de ses PV)/g, '<b class="chiffre">$1$2</b>');
  const fil = $("ar-fil"); fil.appendChild(li);
  while (fil.children.length > 5) fil.firstElementChild.remove();
}
function banniere(l, camp) {
  // le nom de l'ulti devient le titre du panneau, avec un éclat doré (ou rouge pour l'adversaire)
  const m = l.match(/lance (.+?)(?: :| sur |,|$)/);
  const b = $("ar-banniere"), p = $("ar-panneau");
  b.innerHTML = `<span>${esc(m ? m[1] : "Ulti !")}</span>`;
  b.className = "ar-ulti " + (camp === 0 ? "moi" : "eux");
  p.classList.remove("eclat-moi", "eclat-eux"); void p.offsetWidth; p.classList.add(camp === 0 ? "eclat-moi" : "eclat-eux");
}

// ---------- effets d'ulti ----------
// Dessinés en direct sur un calque par-dessus l'arène. Chaque ulti peut avoir le sien ; les autres gardent l'animation simple.
const fx = { parts: [], boucle: false };
function calqueFx() {
  let cv = $("ar-fx");
  if (!cv) { cv = document.createElement("canvas"); cv.id = "ar-fx"; cv.className = "ar-fx"; $("arene").appendChild(cv); }
  const d = Math.min(devicePixelRatio || 1, 2);
  if (cv.width !== Math.round(innerWidth * d)) { cv.width = Math.round(innerWidth * d); cv.height = Math.round(innerHeight * d); }
  return cv;
}
function animerFx() {
  if (fx.boucle) return;
  fx.boucle = true;
  const cv = calqueFx(), ctx = cv.getContext("2d"), d = cv.width / innerWidth;
  let avant = performance.now();
  const tour = (t) => {
    const dt = Math.min(50, t - avant) * arVitesse; avant = t;
    ctx.setTransform(d, 0, 0, d, 0, 0); ctx.clearRect(0, 0, innerWidth, innerHeight);
    ctx.globalCompositeOperation = "lighter";
    fx.parts = fx.parts.filter((p) => (p.vie -= dt) > 0);
    for (const p of fx.parts) p.dessin(ctx, p, dt);
    ctx.globalCompositeOperation = "source-over";
    if (fx.parts.length) requestAnimationFrame(tour); else { fx.boucle = false; ctx.clearRect(0, 0, innerWidth, innerHeight); }
  };
  requestAnimationFrame(tour);
}
const centre = (el, dy = 0.45) => { const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height * dy, w: r.width, h: r.height }; };
const hasard = (a, b) => a + Math.random() * (b - a);
function secousse(force) {
  const sc = document.querySelector(".ar-scene");
  sc.animate([{ transform: "none" }, { transform: `translate(${force}px,${-force / 2}px)` }, { transform: `translate(${-force}px,${force / 2}px)` }, { transform: "none" }],
    { duration: 220 / arVitesse });
}
// une balle : un trait doré qui file de la source à la cible, puis une gerbe d'étincelles à l'impact
function balle(de, vers, retard) {
  const duree = 260;
  fx.parts.push({ vie: duree + retard, max: duree + retard, dessin: (ctx, p) => {
    const t = 1 - (p.vie - 0) / p.max, k = (t * p.max - retard) / duree;
    if (k < 0) return;
    if (k >= 1) { if (!p.touche) { p.touche = true; for (let i = 0; i < 7; i++) etincelle(vers.x, vers.y); } return; }
    const x = de.x + (vers.x - de.x) * k, y = de.y + (vers.y - de.y) * k;
    const qx = de.x + (vers.x - de.x) * Math.max(0, k - 0.28), qy = de.y + (vers.y - de.y) * Math.max(0, k - 0.28);
    const g = ctx.createLinearGradient(qx, qy, x, y);
    g.addColorStop(0, "rgba(255,190,80,0)"); g.addColorStop(1, "rgba(255,236,170,1)");
    ctx.strokeStyle = g; ctx.lineWidth = 4.5; ctx.shadowColor = "rgba(255,180,60,.9)"; ctx.shadowBlur = 12; ctx.lineCap = "round";
    ctx.beginPath(); ctx.moveTo(qx, qy); ctx.lineTo(x, y); ctx.stroke();
    ctx.fillStyle = "rgba(255,250,220,1)"; ctx.beginPath(); ctx.arc(x, y, 3.6, 0, 6.3); ctx.fill(); ctx.shadowBlur = 0;
  } });
}
function etincelle(x, y) {
  const a = hasard(0, 6.28), v = hasard(0.08, 0.35), vie = hasard(220, 480);
  fx.parts.push({ vie, max: vie, x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v - 0.08, dessin: (ctx, p, dt) => {
    p.x += p.vx * dt; p.y += p.vy * dt; p.vy += 0.0006 * dt;
    const al = p.vie / p.max;
    ctx.fillStyle = `rgba(255,${170 + 60 * al | 0},90,${al})`; ctx.beginPath(); ctx.arc(p.x, p.y, 1.8 + al * 1.6, 0, 6.3); ctx.fill();
  } });
}
function eclair(x, y, r, couleur) {   // le flash rond d'un impact
  fx.parts.push({ vie: 260, max: 260, dessin: (ctx, p) => {
    const al = p.vie / p.max, rr = r * (1.3 - al * 0.5);
    const g = ctx.createRadialGradient(x, y, 0, x, y, rr);
    g.addColorStop(0, `rgba(${couleur},${0.75 * al})`); g.addColorStop(1, `rgba(${couleur},0)`);
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, rr, 0, 6.3); ctx.fill();
  } });
}

// briques communes des effets
function anneau(x, y, rmax, couleur, duree = 520, epais = 6) {   // une onde de choc qui s'élargit
  fx.parts.push({ vie: duree, max: duree, dessin: (ctx, p) => {
    const t = 1 - p.vie / p.max, r = rmax * (0.15 + 0.85 * t), al = 1 - t;
    ctx.strokeStyle = `rgba(${couleur},${al})`; ctx.lineWidth = epais * (1 - t * 0.6);
    ctx.shadowColor = `rgba(${couleur},1)`; ctx.shadowBlur = 18;
    ctx.beginPath(); ctx.ellipse(x, y, r, r * 0.55, 0, 0, 6.3); ctx.stroke(); ctx.shadowBlur = 0;
  } });
}
function rayon(de, vers, duree, coeur, halo, large) {   // un faisceau qui jaillit puis s'éteint
  fx.parts.push({ vie: duree, max: duree, dessin: (ctx, p) => {
    const t = 1 - p.vie / p.max, pousse = Math.min(1, t / 0.25), al = t < 0.6 ? 1 : 1 - (t - 0.6) / 0.4;
    const x = de.x + (vers.x - de.x) * pousse, y = de.y + (vers.y - de.y) * pousse;
    ctx.lineCap = "round";
    ctx.strokeStyle = `rgba(${halo},${0.55 * al})`; ctx.lineWidth = large * (1 + 0.3 * Math.sin(t * 40));
    ctx.shadowColor = `rgba(${halo},1)`; ctx.shadowBlur = 30;
    ctx.beginPath(); ctx.moveTo(de.x, de.y); ctx.lineTo(x, y); ctx.stroke();
    ctx.strokeStyle = `rgba(${coeur},${al})`; ctx.lineWidth = large * 0.3; ctx.shadowBlur = 10;
    ctx.beginPath(); ctx.moveTo(de.x, de.y); ctx.lineTo(x, y); ctx.stroke(); ctx.shadowBlur = 0;
  } });
}
function flamme(x, y, vx, vy, taille) {
  const vie = hasard(500, 900);
  fx.parts.push({ vie, max: vie, x, y, vx, vy, dessin: (ctx, p, dt) => {
    p.x += p.vx * dt; p.y += p.vy * dt; p.vx *= 0.995;
    const al = p.vie / p.max, r = taille * (1.4 - al * 0.6);
    const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r);
    g.addColorStop(0, `rgba(255,${200 * al + 40 | 0},80,${0.9 * al})`); g.addColorStop(0.5, `rgba(255,90,20,${0.5 * al})`); g.addColorStop(1, "rgba(160,20,0,0)");
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, 6.3); ctx.fill();
  } });
}
const touchees = (c, avant, apres, camp) => c.unites.map((u, k) => k).filter((k) => c.unites[k].camp !== camp && apres[k][0] < avant[k][0]);
const appliquer = (c, ks, apres) => ks.forEach((k) => majUnite(k, c.unites[k], apres[k], true));

// Senna · Ténèbres aveuglantes : un rayon de lumière noire sur chaque ennemi, puis un bouclier sur toute son équipe
async function tenebresAveuglantes(c, qui, avant, apres) {
  const el = $("ar-u" + qui); if (!el) return;
  const camp = c.unites[qui].camp, src = centre(el, 0.3);
  el.animate([{ filter: "none" }, { filter: "brightness(1.6) drop-shadow(0 0 24px #5ff2d8)" }, { filter: "none" }], { duration: 1400 / arVitesse });
  for (let i = 0; i < 16; i++) fx.parts.push({ vie: 500, max: 500, a: i / 16 * 6.28, dessin: (ctx, p) => {   // la lumière se concentre sur Senna
    const t = 1 - p.vie / p.max, r = 90 * (1 - t);
    ctx.fillStyle = `rgba(120,255,230,${t})`; ctx.beginPath(); ctx.arc(src.x + Math.cos(p.a) * r, src.y + Math.sin(p.a) * r * 0.7, 3, 0, 6.3); ctx.fill();
  } });
  animerFx(); await pause(450 / arVitesse);
  const cibles = c.unites.map((u, k) => k).filter((k) => c.unites[k].camp !== camp && avant[k][0] > 0);
  for (const k of cibles) {
    const v = centre($("ar-u" + k), 0.42);
    rayon(src, v, 750, "235,255,250", "40,200,180", 22);
    setTimeout(() => { eclair(v.x, v.y, v.w * 0.55, "90,240,215"); for (let i = 0; i < 8; i++) etincelle(v.x, v.y); }, 180 / arVitesse);
  }
  animerFx(); await pause(200 / arVitesse);
  secousse(5);
  appliquer(c, cibles, apres);
  await pause(450 / arVitesse);
  const allies = c.unites.map((u, k) => k).filter((k) => c.unites[k].camp === camp && apres[k][0] > 0);
  for (const k of allies) {   // le bouclier se pose
    const a = centre($("ar-u" + k), 0.5);
    anneau(a.x, a.y, a.w * 0.75, "150,220,255", 700, 5);
    $("ar-u" + k).animate([{ filter: "none" }, { filter: "drop-shadow(0 0 18px #9fdcff) brightness(1.25)" }, { filter: "none" }], { duration: 900 / arVitesse });
  }
  appliquer(c, allies, apres);
  animerFx(); await pause(500 / arVitesse);
}

// Jax · Contre-attaque : il bondit sur sa cible, onde de choc à l'impact, la cible est étourdie, et il se met en garde
async function contreAttaque(c, qui, avant, apres) {
  const el = $("ar-u" + qui); if (!el) return;
  const camp = c.unites[qui].camp;
  const k = touchees(c, avant, apres, camp)[0] ?? c.unites.findIndex((u, i) => u.camp !== camp && avant[i][0] > 0);
  if (k < 0) return;
  const de = centre(el, 0.5), cible = centre($("ar-u" + k), 0.5);
  const dx = cible.x - de.x, dy = (cible.y - de.y) * 0.72;
  const saut = el.animate([{ transform: "none", offset: 0 }, { transform: `translate(${dx * 0.2}px,${dy * 0.2 - 50}px) rotate(-8deg) scale(1.12)`, offset: 0.35 },
    { transform: `translate(${dx}px,${dy}px) rotate(6deg) scale(1.15)`, offset: 0.55 }, { transform: `translate(${dx}px,${dy}px) scale(1.1)`, offset: 0.7 }, { transform: "none", offset: 1 }],
    { duration: 1300 / arVitesse, easing: "ease-in-out" });
  el.style.zIndex = 5;
  await pause(1300 * 0.55 / arVitesse);
  anneau(cible.x, cible.y + cible.h * 0.15, cible.w * 1.1, "255,215,120", 600, 8);
  eclair(cible.x, cible.y, cible.w * 0.7, "255,230,160");
  for (let i = 0; i < 18; i++) etincelle(cible.x, cible.y);
  for (let i = 0; i < 3; i++) fx.parts.push({ vie: 1100, max: 1100, a: i * 2.09, dessin: (ctx, p, dt) => {   // étoiles d'étourdissement
    p.a += 0.006 * dt; const al = Math.min(1, p.vie / 300), x = cible.x + Math.cos(p.a) * 30, y = cible.y - cible.h * 0.42 + Math.sin(p.a) * 9;
    ctx.fillStyle = `rgba(255,230,120,${al})`; ctx.font = "bold 18px sans-serif"; ctx.fillText("★", x - 7, y + 6);
  } });
  animerFx(); secousse(8);
  appliquer(c, [k], apres);
  await pause(1300 * 0.45 / arVitesse);
  el.style.zIndex = "";
  anneau(de.x, de.y, de.w * 0.7, "180,220,255", 600, 4);   // en garde : il bloquera les prochaines attaques
  el.animate([{ filter: "none" }, { filter: "drop-shadow(0 0 16px #b8dcff)" }, { filter: "none" }], { duration: 800 / arVitesse });
  animerFx(); await pause(350 / arVitesse);
  return saut;
}

// Drake infernal · Souffle dévastateur : une vague de feu qui déferle sur toute l'équipe adverse
async function souffleDevastateur(c, qui, avant, apres) {
  const el = $("ar-u" + qui); if (!el) return;
  const camp = c.unites[qui].camp, src = centre(el, camp === 1 ? 0.75 : 0.25);
  el.animate([{ transform: "none" }, { transform: "scale(1.05) translateY(-8px)" }, { transform: "scale(1.08) translateY(10px)" }, { transform: "none" }], { duration: 1600 / arVitesse });
  eclair(src.x, src.y, src.w * 0.4, "255,140,40");
  const cibles = c.unites.map((u, k) => k).filter((k) => c.unites[k].camp !== camp && avant[k][0] > 0);
  const zone = cibles.map((k) => centre($("ar-u" + k), 0.45));
  const xmin = Math.min(...zone.map((z) => z.x - z.w / 2)), xmax = Math.max(...zone.map((z) => z.x + z.w / 2)), ycible = zone[0]?.y ?? src.y + 300;
  for (let n = 0; n < 7; n++) {   // le souffle sort par bouffées
    for (let i = 0; i < 14; i++) {
      const tx = hasard(xmin, xmax), duree = hasard(520, 700);
      flamme(src.x + hasard(-30, 30), src.y, (tx - src.x) / duree, (ycible - src.y) / duree, hasard(14, 30));
    }
    animerFx(); await pause(90 / arVitesse);
    if (n === 3) secousse(10);
  }
  await pause(250 / arVitesse);
  for (const z of zone) { eclair(z.x, z.y, z.w * 0.8, "255,110,30"); for (let i = 0; i < 10; i++) etincelle(z.x, z.y); }
  for (const k of cibles) $("ar-u" + k).animate([{ filter: "none" }, { filter: "sepia(1) saturate(4) hue-rotate(-20deg) brightness(1.3)" }, { filter: "none" }], { duration: 700 / arVitesse });
  secousse(12);
  appliquer(c, cibles, apres);
  animerFx(); await pause(600 / arVitesse);
}

// Miss Fortune · Barrage de balles (d'après la maquette « 4 vagues de boulets enflammés ») :
// 4 vagues de 17 boulets en éventail, chacun avec sa traînée de feu, qui s'écrasent sur les ennemis
function boulet(de, vers, retard, r) {
  const duree = hasard(380, 470);
  fx.parts.push({ vie: duree + retard + 400, max: duree + retard + 400, trail: [], age: -retard, dessin: (ctx, p, dt) => {
    p.age += dt;
    if (p.age < 0) return;
    const k = Math.min(1, p.age / duree);
    if (k < 1) {   // vol en légère courbe
      const x = de.x + (vers.x - de.x) * k, y = de.y + (vers.y - de.y) * k - Math.sin(k * Math.PI) * 30;
      p.trail.unshift([x, y]); if (p.trail.length > 18) p.trail.pop();
      if (Math.random() < 0.35) braise(x, y, 70);
    } else {
      if (!p.touche) { p.touche = true; eclair(vers.x, vers.y, r * 4.5, "255,140,30"); for (let i = 0; i < 6; i++) braise(vers.x, vers.y, 220); }
      p.trail.pop();
    }
    for (let n = p.trail.length - 1; n >= 0; n--) {   // traînée de feu
      const [tx, ty] = p.trail[n], f = 1 - n / p.trail.length, rr = r * (0.25 + 1.35 * f) * 2.1;
      const g = ctx.createRadialGradient(tx, ty, 0, tx, ty, rr);
      g.addColorStop(0, `rgba(255,230,108,${0.72 * f})`); g.addColorStop(0.24, `rgba(255,128,12,${0.72 * f})`);
      g.addColorStop(0.63, `rgba(245,47,0,${0.4 * f})`); g.addColorStop(1, "rgba(255,24,0,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(tx, ty, rr, 0, 6.3); ctx.fill();
    }
    if (k < 1 && p.trail.length) {   // le boulet lui-même, sombre, cerclé de feu
      const [bx, by] = p.trail[0];
      const halo = ctx.createRadialGradient(bx, by, 0, bx, by, r * 3);
      halo.addColorStop(0, "rgba(255,176,58,.42)"); halo.addColorStop(1, "rgba(255,73,0,0)");
      ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(bx, by, r * 3, 0, 6.3); ctx.fill();
      ctx.globalCompositeOperation = "source-over";
      const g = ctx.createRadialGradient(bx - r * 0.35, by - r * 0.45, 1, bx, by, r);
      g.addColorStop(0, "#9c8a75"); g.addColorStop(0.35, "#494541"); g.addColorStop(0.8, "#191919"); g.addColorStop(1, "#050505");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(bx, by, r, 0, 6.3); ctx.fill();
      ctx.strokeStyle = "#f59b3a"; ctx.lineWidth = 1.2; ctx.stroke();
      ctx.globalCompositeOperation = "lighter";
    }
  } });
}
function braise(x, y, v) {
  const a = hasard(0, 6.28), vv = hasard(0.2, 1) * v / 1000, vie = hasard(200, 550);
  fx.parts.push({ vie, max: vie, x, y, vx: Math.cos(a) * vv, vy: Math.sin(a) * vv - 0.05, t: hasard(1, 3), dessin: (ctx, p, dt) => {
    p.x += p.vx * dt; p.y += p.vy * dt; p.vy += 0.00025 * dt;
    const al = p.vie / p.max;
    ctx.fillStyle = `rgba(255,${100 + 120 * al | 0},25,${al})`; ctx.beginPath(); ctx.arc(p.x, p.y, p.t, 0, 6.3); ctx.fill();
  } });
}
async function barrageDeBalles(c, qui, avant, apres) {
  const el = $("ar-u" + qui); if (!el) return;
  const camp = c.unites[qui].camp;
  const cibles = c.unites.map((u, k) => k).filter((k) => c.unites[k].camp !== camp && avant[k][0] > 0);
  if (!cibles.length) return;
  const src = centre(el, camp === 0 ? 0.2 : 0.8);
  const zones = cibles.map((k) => centre($("ar-u" + k), 0.42));
  const gauche = Math.min(...zones.map((z) => z.x - z.w * 0.45)), droite = Math.max(...zones.map((z) => z.x + z.w * 0.45));
  const r = Math.max(5, Math.min(9, innerWidth / 170));
  el.animate([{ transform: "none" }, { transform: `translateY(${camp === 0 ? -14 : 14}px) scale(1.08)` }, { transform: "none" }], { duration: 2400 / arVitesse });
  for (let v = 0; v < 4; v++) {
    for (let i = 0; i < 40; i++) braise(src.x, src.y, 240);   // le coup de feu au départ
    eclair(src.x, src.y, src.w * 0.6, "255,170,60");
    for (let i = 0; i < 17; i++) {   // 17 boulets en éventail sur toute la ligne ennemie
      const f = i / 16, z = zones.reduce((a, b) => (Math.abs(b.x - (gauche + (droite - gauche) * f)) < Math.abs(a.x - (gauche + (droite - gauche) * f)) ? b : a));
      const vers = { x: gauche + (droite - gauche) * f + hasard(-12, 12), y: z.y + hasard(-z.h * 0.25, z.h * 0.25) };
      boulet({ x: src.x, y: src.y }, vers, Math.abs(i - 8) * 6 + v * 0, r + (i % 3));
    }
    animerFx();
    await pause(430 / arVitesse);
    secousse(v === 3 ? 10 : 6);
    for (const k of cibles) {   // les PV descendent vague par vague
      const pv = Math.round(avant[k][0] + (apres[k][0] - avant[k][0]) * (v + 1) / 4);
      majUnite(k, c.unites[k], [pv, apres[k][1], apres[k][2], apres[k][3]], true);
    }
    await pause(260 / arVitesse);
  }
  await pause(250 / arVitesse);
}

const EFFETS = [[/Barrage de balles/, barrageDeBalles], [/Ténèbres aveuglantes/, tenebresAveuglantes],
  [/Contre-attaque/, contreAttaque], [/Souffle dévastateur/, souffleDevastateur]];

// l'arène animée (PixiJS) quand l'ordinateur la gère ; sinon l'arène simple ci-dessous
const titreCombat = (c) => c.mode === "donjon" ? `${c.emoji} ${c.nom}` : `${c.boss ? "Boss · " : ""}Étage ${c.etage}${c.etage > 100 ? " · tour difficile" : ""}`;
function iconesCarte(u) {
  if (u.camp !== 0 || !moi) return [];
  const c = carteDe(u.cid); if (!c) return [];
  return [c.item, c.rune].filter((x) => x && x.icone).map((x) => (ENDEMO ? x.icone.replace(/^\//, "") : x.icone));
}
async function jouerCombat(c) {
  if (window.ArenePixi && ArenePixi.disponible() && !calme()) {
    if ($("arene").open) $("arene").close();
    const ok = await ArenePixi.jouer(c, { titre: titreCombat(c), icones: iconesCarte, fin: (el) => finCombat(c, el),
      fond: "/static/arene_fond.webp", cadreBoss: "/static/cadre_boss.webp", barreBoss: "/static/barre_boss.webp",
      sennaFeuilles: ["/static/senna_ulti_1.webp", "/static/senna_ulti_2.webp"] }).catch(() => false);
    if (ok) return;
  }
  const d = $("arene");
  $("ar-titre").innerHTML = `${esc(titreCombat(c))} <span id="ar-tour">Tour 1</span>`;
  const eux = c.unites.map((u, k) => [u, k]).filter(([u]) => u.camp === 1), nous = c.unites.map((u, k) => [u, k]).filter(([u]) => u.camp === 0);
  $("ar-ennemis").innerHTML = eux.map(([u, k]) => uniteHtml(u, k)).join("");
  $("ar-joueurs").innerHTML = nous.map(([u, k]) => uniteHtml(u, k)).join("");
  $("ar-ennemis").classList.toggle("seul", eux.length === 1);
  c.unites.forEach((u, k) => majUnite(k, u, [u.pv, u.bouclier, u.jauge, u.cout], false));
  $("ar-fil").innerHTML = ""; $("ar-fin").hidden = true; $("ar-fin").innerHTML = "";
  $("ar-banniere").className = "ar-ulti"; $("ar-banniere").innerHTML = "<span>Le combat commence</span>";
  if (!d.open) d.showModal();
  let fini = false;
  arFinir = () => { fini = true; };
  arVitesse = Number(document.querySelector('.ar-vitesse [aria-pressed="true"]')?.dataset.v) || 1;
  await pause(500);
  let prec = c.unites.map((u) => [u.pv, u.bouclier, u.jauge, u.cout]);
  for (const a of c.actions) {
    if (fini) break;
    const u = c.unites[a.a], el = $("ar-u" + a.a);
    $("ar-tour").textContent = "Tour " + a.t;
    const ulti = a.l.some((l) => /^(✨|🔥)/u.test(l));
    if (el && !a.passe) { el.classList.remove("agit", "ulti"); void el.offsetWidth; el.classList.add(ulti ? "ulti" : "agit"); }
    const ligneUlti = ulti && a.l.find((l) => /^(✨|🔥)/u.test(l));
    if (ulti) banniere(ligneUlti, u.camp);
    await pause((ulti ? 380 : 220) / arVitesse);
    a.l.filter((l) => !l.startsWith("💫") || a.passe).forEach(ligneFil);
    const effet = ulti && !fini && arVitesse < 10 && !calme() && EFFETS.find(([re]) => re.test(ligneUlti));
    if (effet) {   // une ulti qui a son animation : les dégâts tombent au rythme de l'effet
      await effet[1](c, a.a, prec, a.e);
      a.e.forEach((e, k) => majUnite(k, c.unites[k], e, false));
      await pause(450 / arVitesse);
    } else {
      a.e.forEach((e, k) => majUnite(k, c.unites[k], e, true));
      await pause((a.passe ? 380 : ulti ? 1050 : 520) / arVitesse);
    }
    prec = a.e;
  }
  const der = c.actions[c.actions.length - 1];
  if (der) { der.e.forEach((e, k) => majUnite(k, c.unites[k], e, false)); $("ar-tour").textContent = "Tour " + der.t; }
  if (c.fin) ligneFil(c.fin);
  await pause(fini ? 100 : 600);
  finCombat(c);
}
function finCombat(c, f = $("ar-fin")) {
  const r = c.recompenses;
  f.className = "ar-fin " + (c.victoire ? "victoire" : "defaite");
  f.innerHTML = `<div class="ar-fin-in"><p class="ar-fin-titre">${c.victoire ? "Victoire" : "Défaite"}</p>
    <p class="ar-fin-sous">${c.mode === "donjon" ? esc(c.nom) : `Étage ${c.etage}`} · ${c.tours} tours</p>
    ${c.mode === "donjon" ? finDonjon(c) : c.victoire && r ? `<ul class="ar-gains"><li>${PIECE}<b>+${nombre(r.golds)}</b> golds</li><li>✨ <b>+${nombre(r.xp)}</b> XP par carte</li>
      ${r.xp_compte ? `<li>⭐ <b>+${nombre(r.xp_compte)}</b> XP de compte</li>` : ""}
      ${(r.montees || []).length ? `<li class="petit">⬆️ ${esc(r.montees.join(", "))}</li>` : ""}
      ${r.niveau ? `<li class="fort">Niveau de compte <b>${r.niveau}</b> ! Un pack de niveau t'attend.</li>` : ""}
      ${r.pack ? (typeof r.pack === "string" ? `<li>🎁 ${esc(r.pack)}</li>` : `<li class="gain-pack">🎁 ${esc(r.pack.titre)} : <b style="color:var(--${r.pack.rarete})">${esc(r.pack.nom)}</b> · ${r.pack.rarete}</li>`) : ""}</ul>`
      : `<ul class="ar-conseils">${(c.conseils || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`}
    <div class="ar-fin-actions">
      ${c.mode === "donjon" && (c.stock > 0 || ENDEMO) ? `<button class="bouton" data-ar="donjon"><i class="orne g"></i>${c.victoire ? "Encore" : "Réessayer"}<i class="orne d"></i></button>` : ""}
      ${c.mode !== "donjon" && !c.victoire && ENDEMO && tourDonnees?.combats?.[String(c.etage + 1)] ? `<button class="bouton" data-ar="victoire"><i class="orne g"></i>Démo : voir une victoire<i class="orne d"></i></button>` : ""}
      ${c.mode !== "donjon" && c.victoire && !ENDEMO ? `<button class="bouton" data-ar="suivant"><i class="orne g"></i>Étage suivant<i class="orne d"></i></button>` : ""}
      ${c.mode !== "donjon" && !c.victoire && !ENDEMO ? `<button class="bouton" data-ar="revanche"><i class="orne g"></i>Réessayer<i class="orne d"></i></button>` : ""}
      <button class="bouton secondaire" data-ar="fermer"><i class="orne g"></i>Fermer<i class="orne d"></i></button>
    </div></div>`;
  f.hidden = false;
}
function fermerArenes() { if ($("arene").open) $("arene").close(); if (window.ArenePixi) ArenePixi.fermer(); }
document.addEventListener("click", (e) => {   // les boutons de l'écran de fin de l'arène animée
  if (!e.target.closest("#arene3d")) return;
  const b = e.target.closest("[data-ar]"); if (!b) return;
  const quoi = b.dataset.ar;
  actionArene(quoi);
});
function actionArene(quoi) {
  if (quoi === "fermer") { fermerArenes(); if (!ENDEMO) { if (location.hash === "#donjons") { donjonsDonnees = null; pageDonjons(); } else pageTour(); } }
  else if (quoi === "victoire") jouerCombat(tourDonnees.combats[String(tourDonnees.prochain + 1)]);
  else if (quoi === "donjon") combattreDonjon(dernierDonjon);
  else combattreTour();
}
$("arene").addEventListener("click", (e) => {
  const v = e.target.closest(".ar-vitesse button");
  if (v) {
    if (v.dataset.v === "fin") { arVitesse = 50; if (arFinir) arFinir(); }
    else { arVitesse = Number(v.dataset.v); document.querySelectorAll(".ar-vitesse button").forEach((b) => b.setAttribute("aria-pressed", b === v)); }
    return;
  }
  const b = e.target.closest("[data-ar]"); if (!b) return;
  actionArene(b.dataset.ar);
});
$("arene").addEventListener("close", () => { if (arFinir) arFinir(); const p = document.querySelector('.ar-vitesse [data-v="1"]'); arVitesse = 1; document.querySelectorAll(".ar-vitesse button").forEach((x) => x.setAttribute("aria-pressed", x === p)); });

// ---------- les donjons ----------
let donjonsDonnees = null, dernierDonjon = 0;
const enHeures = (s) => { const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60); return h ? `${h} h ${String(m).padStart(2, "0")}` : `${Math.max(1, m)} min`; };
async function pageDonjons() {
  const box = $("dj-contenu");
  if (!moi) { box.innerHTML = `<div class="message">Connecte-toi avec Discord pour entrer dans les donjons.<div class="actions">${boutonConnexion()}</div></div>`; return; }
  if (!donjonsDonnees) {
    box.innerHTML = `<p class="nb">Chargement…</p>`;
    const r = await api("/api/donjons").catch(() => ({ ok: false }));
    if (!r.ok) { box.innerHTML = `<p class="nb">${esc(r.d?.erreur || "Les donjons ne sont pas disponibles pour l'instant.")}</p>`; return; }
    donjonsDonnees = r.d;
  }
  const d = donjonsDonnees, ferme = d.niveau < d.requis, stock = moi.composants || {};
  const pips = Array.from({ length: d.max }, (_, k) => `<i class="${k < d.stock ? "plein" : ""}"></i>`).join("");
  box.innerHTML = `<section class="panneau donjons-reserve">
      <div><p class="tour-sur">Victoires en réserve</p><div class="d-pips" aria-label="${d.stock} sur ${d.max}">${pips}</div>
        <p class="d-recharge">${d.stock >= d.max ? "Réserve pleine" : `Prochaine victoire dans <b>${enHeures(d.prochaine)}</b>`}</p></div>
      <ul class="d-regles">
        <li>⚔️ <b>${d.butin}</b> composants par victoire <span>(+1 tous les ${d.palier} étages de la tour)</span></li>
        <li>🛡️ Une défaite ne coûte rien : ta réserve reste intacte.</li>
        <li>🩸 Hémorragie : les soins sont réduits à ${d.hemorragie} %.</li>
      </ul>
    </section>
    ${ferme ? `<div class="message">🔒 Les donjons s'ouvrent au <b>niveau ${d.requis}</b> de compte (tu es niveau ${d.niveau}). Monte la tour pour y arriver.</div>` : ""}
    <div class="donjons-grille">${d.donjons.map((x) => `<section class="panneau donjon">
      <h2><span aria-hidden="true">${x.emoji}</span> ${esc(x.nom)}</h2>
      <div class="d-gardiens">${x.gardiens.map((g) => `<figure>${g.image ? `<img src="${esc(g.image)}" alt="" loading="lazy" data-repli="${esc(g.nom)}">` : `<div class="vide">${esc(g.nom)}</div>`}
        <figcaption><b>${esc(g.nom)}</b><span>${nombre(g.pv)} PV</span></figcaption></figure>`).join("")}</div>
      <p class="d-butin-titre">Butin possible</p>
      <ul class="d-butin">${x.composants.map((c) => `<li><span>${c.emoji}</span>${esc(c.nom)}<small>tu en as ${nombre(stock[c.id] || 0)}</small></li>`).join("")}</ul>
      <button class="bouton grand" data-donjon="${x.numero}"${ferme || d.stock <= 0 ? " disabled" : ""}><i class="orne g"></i>${d.stock <= 0 ? "Réserve vide" : "Entrer"}<i class="orne d"></i></button>
    </section>`).join("")}</div>`;
  box.querySelectorAll("img[data-repli]").forEach((im) => (im.onerror = () => { const v = document.createElement("div"); v.className = "vide"; v.textContent = im.dataset.repli; im.replaceWith(v); }));
  box.querySelectorAll("[data-donjon]").forEach((b) => (b.onclick = () => combattreDonjon(Number(b.dataset.donjon))));
}
async function combattreDonjon(numero) {
  dernierDonjon = numero;
  let c;
  if (ENDEMO) c = donjonsDonnees?.combats?.[String(numero)];
  else {
    const r = await fetch("/api/donjon", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ numero }) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { toast(d.erreur || "Le combat n'a pas pu se lancer.", true); return; }
    c = d.combat; if (d.moi) { moi = d.moi; afficherCompte(); } donjonsDonnees = null;
  }
  if (c) jouerCombat(c);
}
function finDonjon(c) {
  const r = c.recompenses;
  if (!c.victoire || !r) return `<ul class="ar-conseils">${(c.conseils || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
  return `<ul class="ar-gains">${r.composants.map((x) => `<li>${x.emoji} <b>+${x.q}</b> ${esc(x.nom)}</li>`).join("")}
    <li>⭐ <b>+${nombre(r.xp_compte)}</b> XP de compte</li>
    ${r.niveau ? `<li class="fort">Niveau de compte <b>${r.niveau}</b> ! Un pack de niveau t'attend.</li>` : ""}
    <li class="petit">${c.stock > 0 ? `${c.stock} victoire${c.stock > 1 ? "s" : ""} encore en réserve.` : "Ta réserve est vide : la forge t'attend dans « Ma collection »."}</li></ul>`;
}

// ---------- la page « Mes packs » ----------
function offres() {
  const p = (k) => nombre(prix(k));
  return [
    ["gratuit", "Un pack offert toutes les 6 heures.", [["gratuit", "Ouvrir"]]],
    ["normal", `${p("normal")} golds le pack. Le pack de 10 garantit au moins un SR. Le méga tirage donne ${prix("mega_cartes")} cartes, au moins un SSR et un pack UR offert.`,
      [["normal", `1 pack · ${p("normal")}`], ["normal10", `10 packs · ${p("normal10")}`], ["mega", `Méga tirage · ${p("mega")}`]]],
    ["pro", "3 cartes par pack, seulement des équipes que tu as éliminées aux Worlds. Parfois une carte de pro, à équiper comme coach.", [["pro", "Ouvrir"], ["pro5", "Ouvrir x5"]]],
    ["ur", "Un pack UR tous les 50 packs ouverts. Une UR y est garantie au bout d'un certain nombre de packs UR.", [["ur", "Ouvrir"], ["ur5", "Ouvrir x5"]]],
    ["lec", "Les cartes des équipes de la LEC que tu as battues.", [["lec", "Ouvrir"], ["lec5", "Ouvrir x5"]]],
    ["niveau", "Un pack gagné à chaque niveau de compte, avec de meilleurs taux.", [["niveau", "Ouvrir"], ["niveau5", "Ouvrir x5"]]],
  ];
}
async function pagePacks() {
  const box = $("p-contenu");
  if (!moi) {
    box.innerHTML = `<div class="message">Connecte-toi avec Discord pour ouvrir tes packs ici.<div class="actions">${boutonConnexion()}</div></div>`;
    return;
  }
  box.innerHTML = `<div class="boutique">${offres().map(([cle, texte, actions]) => {
    const [, classe, nom, image] = PACKS.find((x) => x[0] === cle);
    const qte = cle === "normal" ? `${PIECE}${nombre(moi.golds)}` : cle === "gratuit" ? attenteGratuit(moi.gratuit_dans ?? 0) : `${nombre(moi.packs[cle] ?? 0)} à ouvrir`;
    const pret = peutOuvrir(cle);
    return `<article class="offre offre-${cle}${pret ? " pret" : " epuise"}">
      <button type="button" class="offre-img" data-pack="${cle}" aria-label="Ouvrir un ${esc(nom.toLowerCase())}"><img src="${image}" alt=""></button>
      <div class="offre-txt"><h2>${esc(nom)}</h2><p class="offre-qte">${qte}</p><p class="offre-desc">${esc(texte)}</p>
        <div class="offre-actions">${actions.map(([k, l], i) => `<button type="button" class="bouton${i ? " secondaire" : ""}${peutOuvrir(k) ? "" : " eteint"}" data-pack="${k}"><i class="orne g"></i>${esc(l)}${["normal", "normal10", "mega"].includes(k) ? PIECE : ""}<i class="orne d"></i></button>`).join("")}</div>
      </div></article>`;
  }).join("")}</div>`;
}
$("p-contenu").addEventListener("click", (e) => { const b = e.target.closest("[data-pack]"); if (b) ouvrirPack(b.dataset.pack); });

$("packs").addEventListener("click", (e) => { const b = e.target.closest("[data-pack]"); if (b) ouvrirPack(b.dataset.pack); });
$("ouverture").addEventListener("click", (e) => {
  const b = e.target.closest("[data-ouv]");
  if (b && b.dataset.ouv === "encore") ouvrirPack(b.dataset.pack);
  else if (b && b.dataset.ouv === "fermer" && !ouvertureEnCours) $("ouverture").close();
});
$("ouverture").addEventListener("cancel", (e) => { if (ouvertureEnCours) e.preventDefault(); });

let accueilFait = false;
async function pageAccueil() {
  const p = new URLSearchParams(location.search);
  if (p.get("erreur") && !$("erreur-connexion")) {
    $("hero-actions").insertAdjacentHTML("beforebegin", `<p id="erreur-connexion" class="chapo erreur">La connexion avec Discord n'a pas marché. Réessaie.</p>`);
    history.replaceState(null, "", "/" + location.hash);
  }
  if (accueilFait) return;
  accueilFait = true;
  const [pub, cartes, classe] = await Promise.all([api("/api/public"), api("/api/cartes"), api("/api/classement")].map((x) => x.catch(() => ({ ok: false }))));
  if (pub.ok) {
    $("vitrine").innerHTML = (pub.d.vitrine || []).map((id) => `<img src="${imageCarte(id)}" alt="">`).join("");
    if ($("atout-cartes")) $("atout-cartes").textContent = `${pub.d.cartes_jeu} cartes, du N à la LR · ${nombre(pub.d.cartes_obtenues)} déjà tirées`;
  }
  if (cartes.ok) {
    catalogue = catalogue || cartes.d;
    const top = [...cartes.d].sort((a, b) => rangMode(a, "worlds") - rangMode(b, "worlds")).slice(0, 4);
    $("une").innerHTML = top.map((c) => vignette(c, `<span class="tier t-${c.tier.worlds.tier}">#${c.tier.worlds.rang}</span>`)).join("");
  }
  if (classe.ok) {
    const liste = classe.d.joueurs.filter((j) => j.niveau > 1).sort((a, b) => b.niveau - a.niveau || b.etage - a.etage).slice(0, 5);
    $("mini-classe").innerHTML = liste.map((j, i) => `<li><a href="#joueur/${esc(j.id)}"><span class="place${i < 3 ? " p" + (i + 1) : ""}">${i + 1}</span>
      <span class="qui">${esc(j.pseudo)}</span><span class="valeur">niv. ${j.niveau}</span></a></li>`).join("");
  }
}
function imageCarte(id) { return `/cartes/${encodeURIComponent(id)}`; }

// ---------- toutes les cartes ----------
let catalogue = null, cFiltre = "", cRecherche = "", cTri = "rarete";
// ---------- les derniers tirages (comme le salon des tirages de Discord) ----------
let cVue = "cartes", filMinuteur = null;
const ilYA = (s) => s < 60 ? "à l'instant" : s < 3600 ? `il y a ${Math.floor(s / 60)} min` : s < 86400 ? `il y a ${Math.floor(s / 3600)} h` : `il y a ${Math.floor(s / 86400)} j`;
let filDemo = [];   // la démo n'a pas de serveur : ses belles cartes tirées s'ajoutent ici
function brancherOngletsCartes() {
  $("c-onglets").querySelectorAll("button").forEach((b) => b.setAttribute("aria-selected", b.dataset.cv === cVue));
  $("cv-cartes").hidden = cVue !== "cartes"; $("cv-tirages").hidden = cVue !== "tirages";
}
$("c-onglets").addEventListener("click", (e) => {
  const b = e.target.closest("[data-cv]"); if (!b) return;
  cVue = b.dataset.cv; brancherOngletsCartes();
  if (cVue === "tirages") afficherTirages();
});
async function afficherTirages() {
  const box = $("cv-tirages");
  clearTimeout(filMinuteur);
  if (!box.innerHTML) box.innerHTML = `<p class="nb">Chargement…</p>`;
  let fil = filDemo;
  if (!ENDEMO) {
    const r = await api("/api/tirages").catch(() => ({ ok: false }));
    if (!r.ok) { box.innerHTML = `<p class="nb">Le fil des tirages n'est pas disponible pour l'instant.</p>`; return; }
    fil = r.d;
  }
  box.innerHTML = `<p class="chapo-fil">Les UR, les LR et les cartes de pros dès qu'un joueur les tire, comme dans le salon des tirages.</p>` + (fil.length ? `<ol class="fil-tirages">${fil.map((t) => {
    const top = t.cartes[0];
    return `<li class="tirage" style="--c:var(--${top ? top.rarete : "SSR"})">
      <div class="tirage-tete"><a href="#joueur/${esc(t.joueur)}" class="tirage-joueur">${esc(t.pseudo)}</a> a tiré ${t.cartes.length + t.coachs.length > 1 ? `${t.cartes.length + t.coachs.length} belles cartes` : top ? `<b style="color:var(--${top.rarete})">${esc(top.nom)}</b>` : "une carte de pro"}<time>${ilYA(t.il_y_a)}</time></div>
      <div class="tirage-cartes">${t.cartes.map((c) => `<button class="tirage-carte" data-carte="${esc(c.id)}" title="${esc(c.nom)} · ${c.rarete}"><img src="${imageCarte(c.id)}" alt="${esc(c.nom)}" loading="lazy"><span style="color:var(--${c.rarete})">${c.rarete}</span></button>`).join("")}
        ${t.coachs.map((x) => x.image ? `<span class="tirage-carte"><img src="${esc(x.image)}" alt="${esc(x.pseudo)}" loading="lazy"><span>Pro</span></span>` : `<span class="tirage-pro">🎙️ ${esc(x.pseudo)}</span>`).join("")}</div>
    </li>`; }).join("")}</ol>` : `<div class="message">Aucune belle carte tirée sur le site pour l'instant. Ouvre des packs dans « Mes packs » : chaque UR, LR ou carte de pro apparaîtra ici pour tout le monde.</div>`);
  box.querySelectorAll("[data-carte]").forEach((b) => (b.onclick = () => { const c = (catalogue || []).find((x) => x.id === b.dataset.carte); if (c) ouvrirFiche(c, false); }));
  if (cVue === "tirages" && location.hash.startsWith("#cartes")) filMinuteur = setTimeout(afficherTirages, 30000);
}

async function pageCartes() {
  brancherOngletsCartes();
  if (cVue === "tirages") afficherTirages();
  if (!catalogue) {
    $("c-grille").innerHTML = `<p class="nb">Chargement…</p>`;
    const r = await api("/api/cartes").catch(() => ({ ok: false }));
    if (!r.ok) { $("c-grille").innerHTML = `<p class="nb">Impossible de charger les cartes.</p>`; return; }
    catalogue = r.d;
  }
  if (!$("c-puces").innerHTML) {
    const presentes = RARETES.filter((x) => catalogue.some((c) => c.rarete === x));
    puces($("c-puces"), [["", "Toutes", "var(--or)"], ...presentes.map((x) => [x, x, `var(--${x})`])], cFiltre, (v) => { cFiltre = v; afficherCartes(); });
  }
  afficherCartes();
}
function afficherCartes() {
  const q = cRecherche.trim().toLowerCase();
  let liste = catalogue.filter((c) => (!cFiltre || c.rarete === cFiltre) && (!q || `${c.nom} ${c.region} ${c.role}`.toLowerCase().includes(q)));
  const ordres = {
    rarete: (a, b) => RANG[a.rarete] - RANG[b.rarete] || a.nom.localeCompare(b.nom),
    nom: (a, b) => a.nom.localeCompare(b.nom),
    worlds: (a, b) => rangMode(a, "worlds") - rangMode(b, "worlds"),
    pvp: (a, b) => rangMode(a, "pvp") - rangMode(b, "pvp"),
    boss: (a, b) => rangMode(a, "boss") - rangMode(b, "boss"),
  };
  liste = [...liste].sort(ordres[cTri]);
  const mode = MODES[cTri] ? cTri : null;
  $("c-nb").textContent = `${liste.length} carte${liste.length > 1 ? "s" : ""}`;
  $("c-grille").innerHTML = liste.map((c) => vignette(c, mode && c.tier?.[mode] ? `<span class="tier t-${c.tier[mode].tier}">${c.tier[mode].tier}</span>` : "")).join("")
    || `<p class="nb">Aucune carte ne correspond.</p>`;
}

// ---------- classement ----------
const CLASSEMENTS = {
  niveau: { titre: "Niveau", val: (j) => j.niveau, txt: (j) => `niveau ${j.niveau}` },
  etage: { titre: "Tour", val: (j) => j.etage, txt: (j) => `étage ${j.etage}` },
  arene: { titre: "Arène", val: (j) => j.arene, txt: (j) => `${nombre(j.arene)} points` },
  worlds: { titre: "Worlds", val: (j, eq) => j.titres * 100 + (j.worlds ? eq.indexOf(j.worlds) + 1 : 0), txt: (j) => j.titres ? `👑 ${j.titres} titre${j.titres > 1 ? "s" : ""}` : j.worlds ? `a battu ${esc(j.worlds)}` : "pas encore joué" },
  collection: { titre: "Collection", val: (j) => j.lr * 10000 + j.ur * 100 + j.cartes, txt: (j) => `${j.cartes} cartes · ${j.ur} UR${j.lr ? ` · ${j.lr} LR` : ""}` },
};
let classementDonnees = null, classementActif = "niveau";
async function pageClassement() {
  if (!classementDonnees) {
    const r = await api("/api/classement").catch(() => ({ ok: false }));
    if (!r.ok) { $("k-liste").innerHTML = `<p class="nb">Impossible de charger le classement.</p>`; return; }
    classementDonnees = r.d;
    $("k-onglets").innerHTML = Object.entries(CLASSEMENTS).map(([k, c]) => `<button role="tab" data-k="${k}" aria-selected="${k === classementActif}">${c.titre}</button>`).join("");
    $("k-onglets").onclick = (e) => {
      const b = e.target.closest("button"); if (!b) return;
      classementActif = b.dataset.k;
      $("k-onglets").querySelectorAll("button").forEach((x) => x.setAttribute("aria-selected", x === b));
      afficherClassement();
    };
  }
  afficherClassement();
}
function afficherClassement() {
  const c = CLASSEMENTS[classementActif], eq = classementDonnees.equipes_worlds;
  const liste = classementDonnees.joueurs.filter((j) => j.niveau > 1).sort((a, b) => c.val(b, eq) - c.val(a, eq) || b.niveau - a.niveau);
  $("k-liste").innerHTML = liste.map((j, i) => `<li><a href="#joueur/${esc(j.id)}">
    <span class="place${i < 3 ? " p" + (i + 1) : ""}">${i + 1}</span><span class="qui">${esc(j.pseudo)}</span>
    <span class="valeur">${c.txt(j)}</span></a></li>`).join("");
}

// ---------- profil d'un joueur ----------
let profilCartes = [];
async function pageJoueur(id) {
  $("j-contenu").innerHTML = `<p class="nb" style="padding-top:30px">Chargement…</p>`;
  const r = await api(`/api/joueur/${encodeURIComponent(id)}`).catch(() => ({ ok: false }));
  if (!r.ok) { $("j-contenu").innerHTML = `<div class="message"><h2>Joueur introuvable</h2><p><a href="#classement">Retour au classement</a></p></div>`; return; }
  const j = r.d;
  profilCartes = [...j.equipe, ...j.vitrine];
  const rar = RARETES.filter((x) => j.raretes[x]).map((x) => `<span><b style="color:var(--${x})">${j.raretes[x]}</b> ${x}</span>`).join("");
  $("j-contenu").innerHTML = `<p class="retour"><a href="#classement">← Classement</a></p>
    <div class="profil"><div><h1>${esc(j.pseudo)}</h1>
      <div class="stats"><span>⭐ niveau <b>${j.niveau}</b></span><span>🏰 étage <b>${j.etage}</b></span><span>⚔️ arène <b>${nombre(j.arene)}</b></span>
      <span>🏆 ${j.titres ? `<b>${j.titres}</b> titre${j.titres > 1 ? "s" : ""}` : j.worlds ? `a battu <b>${esc(j.worlds)}</b>` : "pas encore de Worlds"}</span></div>
      <div class="stats">${j.nb_cartes} cartes · ${rar}</div>
      ${moi && String(j.id) !== String(moi.id || "") ? `<button class="bouton secondaire" id="j-ecrire"><i class="orne g"></i>✉️ Envoyer un message<i class="orne d"></i></button>` : ""}</div></div>
    ${j.equipe.length ? `<h2 class="sous-titre">Son équipe</h2><div class="grille j-grille">${j.equipe.map((c) => vignette(c)).join("")}</div>` : ""}
    <h2 class="sous-titre">Ses cartes les plus fortes</h2><div class="grille j-grille">${j.vitrine.map((c) => vignette(c)).join("")}</div>`;
  $("j-contenu").querySelectorAll(".j-grille").forEach((g) => brancherGrille(g, () => profilCartes, false));
  if ($("j-ecrire")) $("j-ecrire").onclick = () => ecrireA(j.id || id, j.pseudo);
}

// ---------- ma collection ----------
let filtre = "", recherche = "", tri = "rarete";
async function pageCollection() {
  if (!moi) await verifierConnexion();
  if (!moi) {
    $("fiche").hidden = true;
    $("message").hidden = false;
    $("message").innerHTML = `<h2>Connecte-toi</h2><p>Connecte-toi avec ton compte Discord pour voir ta collection.</p>${boutonConnexion()}`;
    return;
  }
  $("message").hidden = true;
  $("fiche").hidden = false;
  $("pseudo").textContent = moi.pseudo;
  if (moi.avatar) { $("avatar").src = moi.avatar; $("avatar").hidden = false; }
  const p = moi.packs;
  $("stats").innerHTML = `<span>${PIECE}<b>${nombre(moi.golds)}</b> golds</span><span>⭐ niveau <b>${moi.niveau}</b></span>
    <span>🏰 étage <b>${moi.etage}</b></span><span>📦 <b>${p.pro}</b> pro · <b>${p.ur}</b> UR · <b>${p.lec}</b> LEC · <b>${p.niveau}</b> niveau</span>
    ${moi.titres ? `<span>👑 <b>${moi.titres}</b> titre${moi.titres > 1 ? "s" : ""}</span>` : ""}`;
  const presentes = RARETES.filter((r) => moi.cartes.some((c) => c.rarete === r));
  puces($("puces"), [["", "Toutes", "var(--or)"], ["equipe", "Mon équipe", "var(--texte)"], ...presentes.map((r) => [r, r, `var(--${r})`])], filtre, (v) => { filtre = v; afficherCollection(); });
  afficherCollection();
  brancherOnglets();
  if (sousVue === "equip") afficherEquipement();
}
function afficherCollection() {
  const q = recherche.trim().toLowerCase();
  let liste = moi.cartes.filter((c) => (!filtre || (filtre === "equipe" ? c.equipe : c.rarete === filtre)) && (!q || `${c.nom} ${c.region} ${c.role}`.toLowerCase().includes(q)));
  const ordres = {
    rarete: (a, b) => RANG[a.rarete] - RANG[b.rarete] || b.niveau - a.niveau || a.nom.localeCompare(b.nom),
    niveau: (a, b) => b.niveau - a.niveau || b.etoiles - a.etoiles || RANG[a.rarete] - RANG[b.rarete],
    nom: (a, b) => a.nom.localeCompare(b.nom),
    force: (a, b) => puissance(b) - puissance(a),
    worlds: (a, b) => rangMode(a, "worlds") - rangMode(b, "worlds"),
  };
  liste = [...liste].sort(ordres[tri]);
  $("nb").textContent = `${liste.length} carte${liste.length > 1 ? "s" : ""}` + (liste.length !== moi.cartes.length ? ` sur ${moi.cartes.length}` : "");
  $("grille").innerHTML = liste.map((c) => vignette(c, `${c.equipe ? `<span title="Dans ton équipe">🛡️</span>` : ""}${c.item ? `<span title="${esc(c.item.nom)}">${ico(c.item, "ico-mini")}</span>` : ""}${c.rune ? `<span title="${esc(c.rune.nom)}">${ico(c.rune, "ico-mini")}</span>` : ""}`)).join("")
    || `<p class="nb">Aucune carte ne correspond.</p>`;
}

// ---------- équipe et équipement (Ma collection) ----------
const ENDEMO = typeof DEMO !== "undefined" && DEMO;
let sousVue = "cartes";
const carteDe = (id) => moi.cartes.find((c) => c.id === id);

function brancherOnglets() {
  const o = $("col-onglets");
  o.querySelectorAll("button").forEach((b) => b.setAttribute("aria-selected", b.dataset.v === sousVue));
  $("vue-cartes").hidden = sousVue !== "cartes";
  $("vue-equip").hidden = sousVue !== "equip";
  $("vue-forge").hidden = sousVue !== "forge";
  o.onclick = (e) => {
    const b = e.target.closest("button"); if (!b) return;
    sousVue = b.dataset.v;
    brancherOnglets();
    afficherSousVue();
  };
}

function afficherSousVue() {
  if (sousVue === "equip") afficherEquipement(); else if (sousVue === "forge") afficherForge(); else afficherCollection();
}

// ---------- la forge ----------
// Les règles viennent du bot (recettes, coûts, niveaux) ; le site calcule ce qui est faisable, le serveur vérifie et forge.
function etatForge() {
  const R = moi.forge; if (!R) return [];
  const stock = moi.composants || {};
  return Object.entries(R.recettes).map(([id, r]) => {
    const ex = moi.sac.filter((x) => x.id.split("~")[0] === id).sort((a, b) => a.niveau - b.niveau);
    const cible = ex.find((x) => x.niveau < R.max);
    const n = cible ? cible.niveau + 1 : 1;
    const cout = r.composants.map((c) => ({ id: c, ...R.composants[c], q: R.quantites[n - 1], a: stock[c] || 0 }));
    return { id, ...r, n, cible, exemplaires: ex.length, cout, faisable: cout.every((c) => c.a >= c.q), effet: r.effets[n - 1], avant: cible ? r.effets[cible.niveau - 1] : null };
  });
}
function afficherForge() {
  const v = $("vue-forge"), R = moi.forge;
  if (!R) { v.innerHTML = `<p class="nb">La forge n'est pas disponible pour l'instant.</p>`; return; }
  const stock = moi.composants || {};
  const recettes = etatForge().sort((a, b) => b.faisable - a.faisable);
  const nbOk = recettes.filter((r) => r.faisable).length;
  v.innerHTML = `<section class="bloc-equip">
      <div class="tete-equip"><h2>Tes composants</h2><p>Ils se gagnent dans les donjons. Un item demande deux composants : <b>${R.quantites.join(", ")}</b> de chaque pour les niveaux ${R.quantites.map((_, k) => k + 1).join(", ")}.</p></div>
      <ul class="forge-comps">${Object.entries(R.composants).map(([id, c]) => `<li class="${stock[id] ? "" : "zero"}">
        <span class="emo">${c.emoji}</span><div><b>${nombre(stock[id] || 0)}</b> ${esc(c.nom)}<small>${esc(c.donjon)}</small></div></li>`).join("")}</ul>
    </section>
    <section class="bloc-equip">
      <div class="tete-equip"><h2>Recettes</h2><p>${nbOk ? `<b>${nbOk}</b> ${nbOk > 1 ? "recettes sont prêtes" : "recette est prête"}. ` : ""}Reforger un item l'améliore jusqu'au niveau ${R.max} ; au maximum, tu en forges un autre exemplaire pour un autre champion.</p></div>
      <div class="forge-grille">${recettes.map(carteRecette).join("")}</div>
    </section>`;
}
function carteRecette(r) {
  const etiquette = r.cible ? `Niv. ${r.cible.niveau} → ${r.n}` : r.exemplaires ? `Exemplaire ${r.exemplaires + 1}` : "Nouveau";
  const action = r.cible ? `Améliorer au niveau ${r.n}` : r.exemplaires ? "Forger un autre exemplaire" : "Forger";
  return `<article class="recette${r.faisable ? " prete" : ""}">
    <div class="recette-tete"><span class="emo grande">${ico(r, "ico-grand")}</span><div><h3>${esc(r.nom)}</h3><span class="recette-niv">${etiquette}</span></div></div>
    <p class="recette-effet">${r.avant ? `<span class="avant">${esc(r.avant)}</span><span class="fleche" aria-hidden="true">→</span>` : ""}<b>${esc(r.effet)}</b></p>
    <ul class="recette-cout">${r.cout.map((c) => `<li class="${c.a >= c.q ? "ok" : "manque"}"><span>${c.emoji} ${esc(c.nom)}</span><b>${nombre(c.a)} / ${c.q}</b></li>`).join("")}</ul>
    <button class="bouton${r.faisable ? "" : " secondaire"}" data-act="forger" data-id="${esc(r.id)}"${r.faisable ? "" : " disabled"}><i class="orne g"></i>${r.faisable ? action : "Composants manquants"}<i class="orne d"></i></button>
  </article>`;
}
async function forger(id) {
  const r = etatForge().find((x) => x.id === id); if (!r || !r.faisable) return;
  try {
    let message;
    if (ENDEMO) {   // la démo applique les mêmes règles en mémoire
      r.cout.forEach((c) => { moi.composants[c.id] -= c.q; });
      if (r.cible) { r.cible.niveau = r.n; r.cible.effet = r.effet; }
      else moi.sac.push({ id: r.exemplaires ? `${id}~${r.exemplaires + 1}` : id, nom: r.nom, emoji: r.emoji, icone: r.icone, niveau: 1, effet: r.effet, carte: "" });
      message = r.cible ? `${r.nom} passe au niveau ${r.n} !` : `${r.nom} est fabriqué ! Équipe-le sur un champion.`;
      simuler("/api/item", {});
    } else {
      const rep = await fetch("/api/forger", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ item: id }) });
      const d = await rep.json().catch(() => ({}));
      if (!rep.ok) throw new Error(d.erreur || "La forge n'a pas pu travailler. Réessaie.");
      message = d.message_forge; moi = d;
    }
    toast("⚒️ " + message + (ENDEMO ? " (démo : rien n'est enregistré)" : ""));
    afficherCompte(); afficherForge();
    const carte = document.querySelector(`.recette [data-id="${CSS.escape(id)}"]`)?.closest(".recette");
    if (carte && !calme()) carte.animate([{ boxShadow: "0 0 0 0 #f0c46a00", transform: "scale(1)" }, { boxShadow: "0 0 40px 6px #f0c46a90", transform: "scale(1.03)" }, { boxShadow: "0 0 0 0 #f0c46a00", transform: "scale(1)" }], { duration: 700 });
  } catch (e) { toast(e.message, true); }
}

function toast(texte, erreur) {
  const t = $("toast");
  t.textContent = texte; t.classList.toggle("erreur", !!erreur); t.hidden = false;
  clearTimeout(toast.minuteur);
  toast.minuteur = setTimeout(() => (t.hidden = true), 3200);
}

// La démo publiée n'a pas de serveur : elle applique les mêmes règles en mémoire.
function simuler(chemin, corps) {
  if (chemin === "/api/equipe") {
    const ok = corps.cartes.filter((id) => carteDe(id));
    if (ok.length < 1 || ok.length > 3) throw new Error("Une équipe, c'est de 1 à 3 cartes que tu possèdes.");
    moi.equipe = ok;
  } else if (chemin === "/api/item") {
    if (corps.carte) moi.sac.forEach((x) => { if (x.carte === corps.carte) x.carte = ""; });
    const it = moi.sac.find((x) => x.id === corps.item); if (it) it.carte = corps.carte;
  } else {
    const p = { ...moi.runes_portees }; delete p[corps.carte];
    if (corps.rune !== "-") {
      const n = (moi.runes.find((r) => r.id === corps.rune) || {}).nombre || 0;
      const autres = Object.keys(p).filter((k) => p[k] === corps.rune);
      while (autres.length && autres.length >= n) delete p[autres.shift()];
      if (Object.keys(p).length >= 3) throw new Error("Tu as déjà 3 runes équipées : retires-en une d'abord.");
      p[corps.carte] = corps.rune;
    }
    moi.runes_portees = p;
  }
  moi.cartes.forEach((c) => {
    c.equipe = moi.equipe.includes(c.id);
    const it = moi.sac.find((x) => x.carte === c.id);
    c.item = it ? { nom: it.nom, emoji: it.emoji, icone: it.icone, niveau: it.niveau, effet: it.effet } : null;
    const r = moi.runes_portees[c.id] && moi.runes.find((x) => x.id === moi.runes_portees[c.id]);
    c.rune = r ? { nom: r.nom, emoji: r.emoji, icone: r.icone, effet: r.effet } : null;
  });
  return moi;
}

// Démo : un tirage au hasard parmi les cartes du jeu (les vrais taux et garanties sont ceux du bot).
const TAUX_DEMO = { normal: { SR: 72, SSR: 25, UR: 3 }, gratuit: { SR: 80, SSR: 19, UR: 1 }, niveau: { SR: 55, SSR: 40, UR: 5 }, ur: { SR: 45, SSR: 45, UR: 10 }, pro: { SR: 60, SSR: 35, UR: 5 }, lec: { SR: 60, SSR: 35, UR: 5 } };
function simulerPack(cle) {
  const base = BASE_PACK(cle);
  const pool = (catalogue || []).filter((c) => ["SR", "SSR", "UR"].includes(c.rarete));
  if (!pool.length) throw new Error("La démo charge encore les cartes : réessaie dans un instant.");
  const nb = cle === "mega" ? prix("mega_cartes") : cle === "normal10" ? 10 : cle.endsWith("5") ? Math.min(5, moi.packs[base]) : 1;
  if (base === "normal") moi.golds -= prix(cle);
  else if (cle === "gratuit") moi.gratuit_dans = 6 * 3600;
  else moi.packs[base] -= nb;
  if (cle === "mega") moi.packs.ur += 1;
  const tirer = () => {
    const taux = TAUX_DEMO[base]; let x = Math.random() * 100, rar = "SR";
    for (const [r, v] of Object.entries(taux)) { if ((x -= v) < 0) { rar = r; break; } }
    const choix = pool.filter((c) => c.rarete === rar);
    const c = choix[Math.floor(Math.random() * choix.length)];
    const deja = moi.cartes.some((m) => m.id === c.id);
    return { ...c, nouvelle: !deja, statut: deja ? "Doublon : +XP de réserve" : "🆕 Nouvelle carte !", en_plus: [] };
  };
  const cartes = Array.from({ length: base === "pro" ? nb * 3 : nb }, tirer);
  const belles = cartes.filter((c) => ["UR", "LR"].includes(c.rarete));
  if (belles.length) filDemo.unshift({ il_y_a: 0, joueur: "100000000000000001", pseudo: moi.pseudo, cartes: belles.map((c) => ({ id: c.id, nom: c.nom, rarete: c.rarete })), coachs: [] });
  return { ...moi, tirage: { pack: cle, cartes, coachs: [], ouverts: nb, message: cle === "mega" ? "💎 Un pack UR t'est offert avec le méga tirage." : "" } };
}

async function changer(chemin, corps, message) {
  try {
    if (ENDEMO) simuler(chemin, corps);
    else {
      const r = await fetch(chemin, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corps) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.erreur || "Le changement n'a pas pu être enregistré.");
      moi = d;
    }
    toast(message + (ENDEMO ? " (démo : rien n'est enregistré)" : ""));
  } catch (e) {
    toast(e.message, true);
  }
  afficherCompte();
  afficherSousVue();
  const ouverte = $("detail").open && $("detail").dataset.id;
  if (ouverte && carteDe(ouverte)) ouvrirFiche(carteDe(ouverte), true);
}

const nomCarte = (id) => (carteDe(id) || { nom: id }).nom;
const optionsItems = (carte) => `<option value="">Aucun item</option>` + moi.sac.map((x) =>
  `<option value="${esc(x.id)}"${x.carte === carte ? " selected" : ""}>${x.emoji} ${esc(x.nom)} niv. ${x.niveau}${x.carte && x.carte !== carte ? ` (sur ${esc(nomCarte(x.carte))})` : ""}</option>`).join("");
const optionsRunes = (carte) => `<option value="-">Aucune rune</option>` + moi.runes.map((r) =>
  `<option value="${esc(r.id)}"${moi.runes_portees[carte] === r.id ? " selected" : ""}>${r.emoji} ${esc(r.nom)}${r.nombre > 1 ? ` ×${r.nombre}` : ""}</option>`).join("");

function choisirItem(carte, valeur) {
  const actuel = moi.sac.find((x) => x.carte === carte);
  if (!valeur) return actuel ? changer("/api/item", { item: actuel.id, carte: "" }, `${actuel.nom} retourne dans ton sac.`) : null;
  const it = moi.sac.find((x) => x.id === valeur);
  changer("/api/item", { item: valeur, carte }, `${it.nom} est équipé sur ${nomCarte(carte)}.`);
}
function choisirRune(carte, valeur) {
  const r = moi.runes.find((x) => x.id === valeur);
  changer("/api/rune", { carte, rune: valeur }, valeur === "-" ? `Rune retirée de ${nomCarte(carte)}.` : `${r.nom} est posée sur ${nomCarte(carte)}.`);
}
function basculerEquipe(id) {
  const eq = [...moi.equipe];
  if (eq.includes(id)) {
    if (eq.length === 1) return toast("Ton équipe doit garder au moins une carte.", true);
    changer("/api/equipe", { cartes: eq.filter((x) => x !== id) }, `${nomCarte(id)} quitte ton équipe.`);
  } else {
    if (eq.length >= 3) return toast("Ton équipe est complète (3 cartes) : retires-en une d'abord.", true);
    changer("/api/equipe", { cartes: [...eq, id] }, `${nomCarte(id)} rejoint ton équipe.`);
  }
}
function faireLeader(id) {
  changer("/api/equipe", { cartes: [id, ...moi.equipe.filter((x) => x !== id)] }, `${nomCarte(id)} devient le leader.`);
}

function actionsCarte(c) {
  const dans = moi.equipe.includes(c.id);
  return `<div class="actions-carte">
    <button class="bouton ${dans ? "secondaire" : ""} petit" data-act="equipe" data-id="${esc(c.id)}">${dans ? "Retirer de l'équipe" : "Ajouter à l'équipe"}</button>
    <label class="champ">Item<select data-act="item" data-id="${esc(c.id)}">${optionsItems(c.id)}</select></label>
    ${dans ? `<label class="champ">Rune<select data-act="rune" data-id="${esc(c.id)}">${optionsRunes(c.id)}</select></label>` : `<p class="note">Les runes se posent sur les cartes de ton équipe.</p>`}
  </div>`;
}

function afficherEquipement() {
  const v = $("vue-equip");
  const slots = [0, 1, 2].map((i) => {
    const id = moi.equipe[i], c = id && carteDe(id);
    if (!c) return `<div class="slot vide-slot"><button class="ajouter" data-act="ajouter">＋<span>Ajouter une carte</span></button></div>`;
    return `<div class="slot" style="--c:var(--${c.rarete})">
      ${i === 0 ? `<span class="leader">Leader</span>` : `<button class="lien-or" data-act="leader" data-id="${esc(c.id)}">Mettre en leader</button>`}
      <button class="slot-img" data-act="fiche" data-id="${esc(c.id)}" aria-label="Voir ${esc(c.nom)}">${c.image ? `<img src="${esc(c.image)}" alt="">` : `<div class="vide">${esc(c.nom)}</div>`}</button>
      <div class="nom">${esc(c.nom)}</div><div class="info"><span class="rar">${c.rarete}</span> · niv. ${c.niveau}${c.etoiles ? " · " + etoiles(c.etoiles) : ""}</div>
      <label class="champ">Item<select data-act="item" data-id="${esc(c.id)}">${optionsItems(c.id)}</select></label>
      <label class="champ">Rune<select data-act="rune" data-id="${esc(c.id)}">${optionsRunes(c.id)}</select></label>
      <button class="bouton discret" data-act="equipe" data-id="${esc(c.id)}">Retirer</button>
    </div>`;
  }).join("");
  const nbPortees = Object.keys(moi.runes_portees).length;
  const horsEquipe = Object.keys(moi.runes_portees).filter((k) => !moi.equipe.includes(k));
  v.innerHTML = `<section class="bloc-equip">
      <div class="tete-equip"><h2>Mon équipe</h2><p>La carte en premier est le <b>leader</b>. C'est cette équipe qui joue la tour, les raids, les donjons et l'arène.</p></div>
      <div class="slots">${slots}</div>
    </section>
    <div class="equip-bas">
      <section class="bloc-equip">
        <div class="tete-equip"><h2>Sac d'items</h2><p>Un item par carte. Pour forger ou améliorer un item, passe par l'onglet <b>La forge</b>.</p></div>
        <ul class="liste-sac">${moi.sac.map((x) => `<li><span class="emo">${ico(x, "ico-grand")}</span><div class="sac-txt"><b>${esc(x.nom)}</b> <span class="niv">niv. ${x.niveau}</span><span class="effet">${esc(x.effet)}</span></div>
          <select data-act="sac" data-item="${esc(x.id)}" aria-label="Équiper ${esc(x.nom)} sur">
            <option value="">Dans le sac</option>
            ${moi.cartes.map((c) => `<option value="${esc(c.id)}"${x.carte === c.id ? " selected" : ""}>${moi.equipe.includes(c.id) ? "🛡️ " : ""}${esc(c.nom)}</option>`).join("")}
          </select></li>`).join("") || `<li class="vide-liste">Ton sac est vide : forge ton premier item dans l'onglet La forge, avec les composants des donjons.</li>`}</ul>
      </section>
      <section class="bloc-equip">
        <div class="tete-equip"><h2>Runes</h2><p><b>${nbPortees}/3</b> emplacements utilisés. Un exemplaire de rune se porte sur une seule carte.</p></div>
        <ul class="liste-runes">${moi.runes.map((r) => {
          const sur = Object.keys(moi.runes_portees).filter((k) => moi.runes_portees[k] === r.id);
          return `<li><span class="emo">${ico(r, "ico-grand")}</span><div class="sac-txt"><b>${esc(r.nom)}</b>${r.nombre > 1 ? ` <span class="niv">×${r.nombre}</span>` : ""}<span class="effet">${esc(r.effet)}</span>
            <span class="porte">${sur.length ? "Sur " + sur.map((k) => esc(nomCarte(k))).join(", ") : "Libre"}</span></div></li>`;
        }).join("") || `<li class="vide-liste">Pas encore de rune : bats Ryze dans le raid sur Discord.</li>`}</ul>
        ${horsEquipe.length ? `<p class="note">⚠️ ${horsEquipe.map((k) => esc(nomCarte(k))).join(", ")} ${horsEquipe.length > 1 ? "portent" : "porte"} une rune sans être dans l'équipe : elle prend un emplacement pour rien.
          ${horsEquipe.map((k) => `<button class="lien-or" data-act="rune-off" data-id="${esc(k)}">Retirer de ${esc(nomCarte(k))}</button>`).join(" ")}</p>` : ""}
      </section>
    </div>`;
}

function ouvrirChoix() {
  $("choix-q").value = "";
  remplirChoix();
  $("choix").showModal();
}
function remplirChoix() {
  const q = $("choix-q").value.trim().toLowerCase();
  const liste = moi.cartes.filter((c) => !moi.equipe.includes(c.id) && (!q || c.nom.toLowerCase().includes(q)))
    .sort((a, b) => puissance(b) - puissance(a));
  $("choix-grille").innerHTML = liste.map((c) => vignette(c)).join("") || `<p class="nb">Aucune carte.</p>`;
}

document.addEventListener("change", (e) => {
  const el = e.target;
  if (el.dataset.act === "item") choisirItem(el.dataset.id, el.value);
  else if (el.dataset.act === "rune") choisirRune(el.dataset.id, el.value);
  else if (el.dataset.act === "sac") {
    const it = moi.sac.find((x) => x.id === el.dataset.item);
    changer("/api/item", { item: it.id, carte: el.value }, el.value ? `${it.nom} est équipé sur ${nomCarte(el.value)}.` : `${it.nom} retourne dans ton sac.`);
  }
});
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-act]");
  if (!b || b.tagName === "SELECT") return;
  const act = b.dataset.act, id = b.dataset.id;
  if (act === "equipe") basculerEquipe(id);
  else if (act === "leader") faireLeader(id);
  else if (act === "ajouter") ouvrirChoix();
  else if (act === "fiche") ouvrirFiche(carteDe(id), true);
  else if (act === "forger") forger(id);
  else if (act === "rune-off") changer("/api/rune", { carte: id, rune: "-" }, `Rune retirée de ${nomCarte(id)}.`);
});
$("choix-q").addEventListener("input", remplirChoix);
$("choix-fermer").addEventListener("click", () => $("choix").close());
$("choix").addEventListener("click", (e) => { if (e.target === $("choix")) $("choix").close(); });
$("choix-grille").addEventListener("click", (e) => {
  const b = e.target.closest(".carte"); if (!b) return;
  $("choix").close();
  changer("/api/equipe", { cartes: [...moi.equipe, b.dataset.id] }, `${nomCarte(b.dataset.id)} rejoint ton équipe.`);
});

// ---------- navigation ----------
async function router() {
  const h = location.hash.replace(/^#/, "");
  const [nom, param] = h.split("/");
  if (nom === "mp" && param) {   // le lien reçu sur Discord : on ouvre la conversation
    history.replaceState(null, "", "#");
    const ouvrir = () => (moi ? ecrireA(param) : setTimeout(ouvrir, 400));
    setTimeout(ouvrir, 300);
  }
  const vue = ["cartes", "classement", "collection", "joueur", "packs", "tour", "donjons", "jungle"].includes(nom) ? nom : "accueil";
  document.querySelectorAll(".vue").forEach((s) => (s.hidden = s.id !== `v-${vue}`));
  document.body.dataset.vue = vue;   // les pages intérieures ont leur propre décor
  document.querySelectorAll("nav a").forEach((a) => {
    const actif = a.dataset.vue === vue || (vue === "joueur" && a.dataset.vue === "classement") || (["tour", "donjons", "jungle"].includes(vue) && a.dataset.vue === "pve");
    if (actif) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  if ($("detail").open) $("detail").close();
  if ($("ouverture").open && !ouvertureEnCours) $("ouverture").close();
  window.scrollTo(0, 0);
  if (vue === "accueil") return pageAccueil();
  if (vue === "cartes") return pageCartes();
  if (vue === "classement") return pageClassement();
  if (vue === "joueur") return pageJoueur(param || "");
  if (vue === "collection") return pageCollection();
  if (vue === "packs") return pagePacks();
  document.querySelectorAll("[data-pve]").forEach((a) => { if (a.dataset.pve === vue) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
  if (vue === "tour") return pageTour();
  if (vue === "donjons") return pageDonjons();
  if (vue === "jungle") return pageJungle();
}

brancherGrille($("c-grille"), () => catalogue || [], false);
brancherGrille($("une"), () => catalogue || [], false);
brancherGrille($("grille"), () => (moi ? moi.cartes : []), true);
$("c-q").addEventListener("input", (e) => { cRecherche = e.target.value; afficherCartes(); });
$("c-tri").addEventListener("change", (e) => { cTri = e.target.value; afficherCartes(); });
$("q").addEventListener("input", (e) => { recherche = e.target.value; afficherCollection(); });
$("tri").addEventListener("change", (e) => { tri = e.target.value; afficherCollection(); });
$("fermer").addEventListener("click", () => $("detail").close());
$("detail").addEventListener("click", (e) => { if (e.target === $("detail")) $("detail").close(); });
window.addEventListener("hashchange", router);
verifierConnexion().finally(router);


// ---------- le chat (en bas à droite, pour tous les joueurs connectés) et les messages privés ----------
const chat = { ouvert: false, onglet: "general", dernier: 0, nonLus: 0, mpNonLus: 0, minuteur: null, moi: null, initialise: false,
  conv: null, convPseudo: "", mpDernier: 0, joueurs: null, discord: false };
function chatPret() {
  $("chat").hidden = !moi;
  if (moi && !chat.minuteur) relever();
}
async function relever() {
  clearTimeout(chat.minuteur);
  if (!moi) { chat.minuteur = null; return; }
  if (!ENDEMO) {
    const r = await fetch(`/api/chat?apres=${chat.dernier}`).then((x) => (x.ok ? x.json() : null)).catch(() => null);
    if (r) { chat.moi = r.moi; chat.mpNonLus = r.mp_non_lus || 0; ajouterMessages(r.messages); }
    if (chat.ouvert && chat.onglet === "mp") await (chat.conv ? releverConv() : afficherConversations());
  }
  majPastilles();
  chat.minuteur = setTimeout(relever, chat.ouvert ? 3000 : 15000);
}
function majPastilles() {
  const total = (chat.ouvert && chat.onglet === "general" ? 0 : chat.nonLus) + chat.mpNonLus;
  $("chat-pastille").hidden = chat.ouvert || !total;
  $("chat-pastille").textContent = total > 99 ? "99+" : total || "";
  $("mp-pastille").hidden = !chat.mpNonLus;
  $("mp-pastille").textContent = chat.mpNonLus || "";
}
function bulle(qui, lien, texte, ilYAs, deMoi) {
  const li = document.createElement("li");
  if (deMoi) li.className = "moi";
  li.innerHTML = `<div class="chat-qui">${qui ? `<a href="${lien}">${esc(qui)}</a>` : ""}<time>${ilYA(ilYAs)}</time></div><p></p>`;
  li.querySelector("p").textContent = texte;   // le texte des joueurs n'est jamais interprété comme du HTML
  return li;
}
function ajouterMessages(liste) {
  if (!liste.length) { chat.initialise = true; return; }
  const fil = $("chat-fil"), enBas = fil.scrollHeight - fil.scrollTop - fil.clientHeight < 40;
  fil.querySelector(".chat-vide")?.remove();
  for (const m of liste) {
    if (m.id <= chat.dernier) continue;
    chat.dernier = m.id;
    const deMoi = m.joueur === chat.moi;
    if (!deMoi && chat.initialise && !(chat.ouvert && chat.onglet === "general")) chat.nonLus++;   // les anciens messages, au premier chargement, ne comptent pas
    fil.appendChild(bulle(m.pseudo, `#joueur/${encodeURIComponent(m.joueur)}`, m.texte, m.il_y_a, deMoi));
  }
  while (fil.children.length > 120) fil.firstElementChild.remove();
  if (enBas || chat.ouvert) fil.scrollTop = fil.scrollHeight;
  chat.initialise = true;
  majPastilles();
}
function videSi(fil, texte) {
  if (!fil.querySelector("li")) fil.innerHTML = `<li class="chat-vide">${texte}</li>`;
}
function ouvrirChat(ouvrir) {
  chat.ouvert = ouvrir;
  $("chat-panneau").hidden = !ouvrir;
  $("chat-bouton").setAttribute("aria-expanded", ouvrir);
  $("chat").classList.toggle("ouvert", ouvrir);
  if (ouvrir) {
    choisirOnglet(chat.onglet);
    relever();
  }
  majPastilles();
}
function choisirOnglet(o) {
  chat.onglet = o;
  document.querySelectorAll("[data-co]").forEach((b) => b.setAttribute("aria-selected", b.dataset.co === o));
  $("chat-general").hidden = o !== "general"; $("chat-mp").hidden = o !== "mp";
  if (o === "general") {
    chat.nonLus = 0;
    videSi($("chat-fil"), "Personne n'a encore écrit. Lance la conversation !");
    const fil = $("chat-fil"); fil.scrollTop = fil.scrollHeight;
    setTimeout(() => $("chat-texte").focus(), 50);
  } else if (chat.conv) ouvrirConv(chat.conv, chat.convPseudo);
  else afficherConversations();
  majPastilles();
}
document.querySelectorAll("[data-co]").forEach((b) => (b.onclick = () => choisirOnglet(b.dataset.co)));
$("chat-bouton").addEventListener("click", () => ouvrirChat(!chat.ouvert));
$("chat-fermer").addEventListener("click", () => ouvrirChat(false));
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && chat.ouvert) ouvrirChat(false); });
$("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const champ = $("chat-texte"), texte = champ.value.trim();
  if (!texte) return;
  champ.value = "";
  if (ENDEMO) { chat.moi = "moi"; ajouterMessages([{ id: chat.dernier + 1, joueur: "moi", pseudo: moi.pseudo, texte, il_y_a: 0 }]); return; }
  try {
    const r = await fetch("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ texte, apres: chat.dernier }) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.erreur || "Le message n'est pas parti.");
    ajouterMessages(d.messages || []);
  } catch (err) { champ.value = texte; toast(err.message, true); }
});

// -- les messages privés --
const mpDemo = {};   // la démo garde ses conversations en mémoire
async function listeJoueurs() {
  if (chat.joueurs) return chat.joueurs;
  const r = await api("/api/classement").catch(() => ({ ok: false }));
  chat.joueurs = r.ok ? (r.d.joueurs || []).filter((j) => j.id !== (chat.moi || "")).sort((a, b) => a.pseudo.localeCompare(b.pseudo)) : [];
  return chat.joueurs;
}
async function afficherConversations() {
  $("mp-conv").hidden = true; $("mp-liste").hidden = false;
  let convs = [];
  if (ENDEMO) convs = Object.entries(mpDemo).map(([id, c]) => ({ joueur: id, pseudo: c.pseudo, dernier: c.messages.at(-1).texte, de_moi: true, il_y_a: 0, non_lus: 0 }));
  else {
    const r = await fetch("/api/mp").then((x) => (x.ok ? x.json() : null)).catch(() => null);
    if (!r) { $("mp-liste").innerHTML = `<p class="mp-info">Les messages ne sont pas disponibles pour l'instant.</p>`; return; }
    convs = r.conversations; chat.discord = r.discord;
  }
  const joueurs = await listeJoueurs();
  if (chat.conv || chat.onglet !== "mp" || !chat.ouvert) return;
  $("mp-liste").innerHTML = `<label class="mp-nouveau">Écrire à<select id="mp-choix"><option value="">Choisis un joueur…</option>
      ${joueurs.map((j) => `<option value="${esc(j.id)}">${esc(j.pseudo)}</option>`).join("")}</select></label>
    ${convs.length ? `<ul class="mp-convs">${convs.map((c) => `<li><button data-conv="${esc(c.joueur)}" data-pseudo="${esc(c.pseudo)}" class="${c.non_lus ? "non-lu" : ""}">
        <span class="mp-nom">${esc(c.pseudo)}${c.non_lus ? `<span class="chat-mini">${c.non_lus}</span>` : ""}</span><time>${ilYA(c.il_y_a)}</time>
        <span class="mp-apercu">${c.de_moi ? "Toi : " : ""}<span></span></span></button></li>`).join("")}</ul>`
      : `<p class="mp-info">Aucune conversation pour l'instant. Choisis un joueur pour lui écrire${chat.discord || ENDEMO ? " : il sera aussi prévenu par message privé sur Discord" : ""}.</p>`}`;
  $("mp-liste").querySelectorAll("[data-conv]").forEach((b, k) => { b.querySelector(".mp-apercu span").textContent = convs[k].dernier; b.onclick = () => ouvrirConv(b.dataset.conv, b.dataset.pseudo); });
  $("mp-choix").onchange = (e) => { const j = joueurs.find((x) => x.id === e.target.value); if (j) ouvrirConv(j.id, j.pseudo); };
}
async function ouvrirConv(id, pseudo) {
  if (chat.conv !== id) { chat.mpDernier = 0; $("mp-fil").innerHTML = ""; }
  chat.conv = id; chat.convPseudo = pseudo || chat.convPseudo || "Joueur";
  $("mp-liste").hidden = true; $("mp-conv").hidden = false;
  $("mp-qui").textContent = chat.convPseudo; $("mp-qui").href = `#joueur/${encodeURIComponent(id)}`;
  await releverConv();
  setTimeout(() => $("mp-texte").focus(), 50);
}
function ajouterMp(d) {
  const fil = $("mp-fil");
  if (d.pseudo) { chat.convPseudo = d.pseudo; $("mp-qui").textContent = d.pseudo; }
  fil.querySelector(".chat-vide")?.remove();
  for (const m of d.messages || []) {
    if (m.id <= chat.mpDernier) continue;
    chat.mpDernier = m.id;
    fil.appendChild(bulle("", "", m.texte, m.il_y_a, m.de_moi));
  }
  videSi(fil, `Écris ton premier message à ${esc(chat.convPseudo)}.`);
  fil.scrollTop = fil.scrollHeight;
}
async function releverConv() {
  if (!chat.conv) return;
  if (ENDEMO) { ajouterMp(mpDemo[chat.conv] || { messages: [] }); return; }
  const id = chat.conv;
  const d = await fetch(`/api/mp/${encodeURIComponent(id)}?apres=${chat.mpDernier}`).then((x) => (x.ok ? x.json() : null)).catch(() => null);
  if (d && chat.conv === id) ajouterMp(d);
  const r = await fetch("/api/chat?apres=999999999").then((x) => (x.ok ? x.json() : null)).catch(() => null);   // le compteur de non lus, remis à jour
  if (r) { chat.mpNonLus = r.mp_non_lus || 0; majPastilles(); }
}
$("mp-retour").addEventListener("click", () => { chat.conv = null; afficherConversations(); });
$("mp-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const champ = $("mp-texte"), texte = champ.value.trim();
  if (!texte || !chat.conv) return;
  champ.value = "";
  if (ENDEMO) {
    const c = (mpDemo[chat.conv] = mpDemo[chat.conv] || { pseudo: chat.convPseudo, messages: [] });
    c.messages.push({ id: c.messages.length + 1, de_moi: true, texte, il_y_a: 0 });
    ajouterMp(c); toast(`Message envoyé à ${chat.convPseudo}. Sur le vrai site, il est aussi prévenu sur Discord. (démo)`);
    return;
  }
  try {
    const r = await fetch("/api/mp", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ a: chat.conv, texte, apres: chat.mpDernier }) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.erreur || "Le message n'est pas parti.");
    ajouterMp(d);
  } catch (err) { champ.value = texte; toast(err.message, true); }
});
function ecrireA(id, pseudo) {   // depuis un profil, ou le lien reçu sur Discord
  if (!moi) { toast("Connecte-toi pour envoyer un message.", true); return; }
  chat.conv = null;
  ouvrirChat(true); choisirOnglet("mp"); ouvrirConv(String(id), pseudo);
}
