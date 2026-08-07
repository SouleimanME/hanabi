/** Explosion d'etincelles a un point de l'ecran - la signature "hanabi".
 *
 * Un feu d'artifice miniature declenche a la volee : ajout au panier, mise en
 * favori, validation de commande. C'est un effet imperatif volontairement
 * decouple de React : on ne veut ni re-rendu, ni etat, juste peindre quelques
 * particules par-dessus toute l'interface puis disparaitre.
 *
 * Un unique <canvas> plein ecran est cree a la demande, partage entre tous les
 * appels, et retire du DOM des qu'il n'y a plus rien a animer - aucune boucle
 * d'animation ne tourne quand l'ecran est au repos.
 *
 * Respecte `prefers-reduced-motion` : le mouvement peut declencher des nausees
 * ou des migraines. Dans ce cas on ne degrade pas, on supprime.
 */

import { sparkPalette } from "./palette.js";

let canvas = null;
let ctx = null;
let particles = [];
let raf = 0;
let lastTs = 0;

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

function ensureCanvas() {
  if (canvas) return;
  canvas = document.createElement("canvas");
  canvas.setAttribute("aria-hidden", "true");
  Object.assign(canvas.style, {
    position: "fixed",
    inset: "0",
    width: "100%",
    height: "100%",
    pointerEvents: "none",
    zIndex: "9999",
  });
  document.body.appendChild(canvas);
  ctx = canvas.getContext("2d");
  resize();
}

function resize() {
  if (!canvas) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = window.innerWidth * dpr;
  canvas.height = window.innerHeight * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function teardown() {
  cancelAnimationFrame(raf);
  raf = 0;
  particles = [];
  if (canvas) {
    canvas.remove();
    canvas = null;
    ctx = null;
  }
}

function frame(ts) {
  const dt = Math.min((ts - lastTs) / 16.667, 2.5); // en "trames" de 60 fps, plafonne apres un onglet en veille
  lastTs = ts;

  ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);

  for (const p of particles) {
    p.vy += 0.12 * dt; // gravite
    p.vx *= 0.985; // trainee
    p.x += p.vx * dt;
    p.y += p.vy * dt;
    p.life -= dt;

    const alpha = Math.max(0, p.life / p.max);
    ctx.globalAlpha = alpha;
    ctx.fillStyle = p.color;
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r * (0.4 + 0.6 * alpha), 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;

  particles = particles.filter((p) => p.life > 0);

  if (particles.length > 0) {
    raf = requestAnimationFrame(frame);
  } else {
    teardown();
  }
}

/**
 * Fait exploser un bouquet d'etincelles centre sur (x, y) en pixels ecran.
 *
 * @param {number} x
 * @param {number} y
 * @param {{count?: number, power?: number, colors?: string[]}} [opts]
 */
export function burst(x, y, { count = 26, power = 7, colors } = {}) {
  if (prefersReducedMotion()) return;
  ensureCanvas();

  // Palette lue une fois par gerbe (pas par image) : elle suit le theme actif,
  // ce qui evite des etincelles couleur papier, invisibles en theme clair.
  const palette = colors ?? sparkPalette();

  for (let i = 0; i < count; i++) {
    const angle = (Math.PI * 2 * i) / count + Math.random() * 0.4;
    const speed = power * (0.5 + Math.random());
    const max = 34 + Math.random() * 26;
    particles.push({
      x,
      y,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed - 1.5, // leger elan vers le haut
      r: 1.6 + Math.random() * 2.4,
      life: max,
      max,
      color: palette[(Math.random() * palette.length) | 0],
    });
  }

  if (!raf) {
    lastTs = performance.now();
    raf = requestAnimationFrame(frame);
  }
}

/** Declenche une explosion centree sur un element du DOM. */
export function burstFromElement(el, opts) {
  if (!el) return;
  const r = el.getBoundingClientRect();
  burst(r.left + r.width / 2, r.top + r.height / 2, opts);
}

if (typeof window !== "undefined") {
  window.addEventListener("resize", resize);
}
