/** Salve d'accueil - quelques feux d'artifice a l'arrivee, puis plus rien.
 *
 * Le nom "Hanabi" (花火, "fleurs de feu") promet des feux d'artifice ; on tient
 * la promesse des la premiere seconde. Mais une animation PERPETUELLE avait un
 * cout perpetuel : la toile se redessinait a chaque image tant que le hero
 * restait visible, c'est-a-dire tout le temps passe en haut de page - la ou le
 * profilage montrait du rouge.
 *
 * On tire donc une breve salve de quelques fusees au chargement, puis la boucle
 * s'arrete DEFINITIVEMENT : plus aucune image n'est calculee, le haut de page ne
 * coute plus rien. Le geste de marque est preserve, la depense continue non.
 *
 * La salve se met en pause si l'onglet passe en arriere-plan ou si le hero sort
 * du champ avant sa fin - inutile de derouler un spectacle que personne ne
 * regarde -, et ne demarre pas du tout si l'utilisateur a demande a limiter les
 * animations.
 */
import { useEffect, useRef } from "react";
import { useReducedMotion } from "../../hooks/useReducedMotion.js";
import { sparkPalette, sparkRender } from "../../lib/palette.js";

// Nombre de fusees de la salve. Assez pour un accueil, assez peu pour que tout
// soit retombe en cinq a six secondes.
const SALVE = 5;

export function Fireworks({ theme }) {
  const canvasRef = useRef(null);
  const reduced = useReducedMotion();

  useEffect(() => {
    if (reduced) return;
    // Palette et mode de rendu relus a chaque changement de theme : le melange
    // additif ne se voit pas sur fond clair (voir lib/palette.js).
    const COLORS = sparkPalette();
    const { blend, alpha: baseAlpha, radius } = sparkRender();
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const parent = canvas.parentElement;

    let width = 0;
    let height = 0;
    let dpr = 1;
    const rockets = [];
    const sparks = [];
    let raf = 0;
    let nextLaunch = 0;
    let tirsRestants = SALVE; // fusees encore a lancer
    let running = true; // onglet visible ET hero a l'ecran
    let termine = false; // vrai une fois la salve entierement retombee

    function measure() {
      // Resolution plafonnee a 1,5 : des points lumineux de un a deux pixels en
      // melange additif n'ont aucun contour franc a preserver, et le
      // reechantillonnage ne fait que les adoucir. On dessine ainsi 44 % de
      // pixels en moins qu'en densite double, sans difference perceptible.
      dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      width = parent.clientWidth;
      height = parent.clientHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(parent);

    function launch() {
      const x = width * (0.15 + Math.random() * 0.7);
      const targetY = height * (0.15 + Math.random() * 0.4);
      rockets.push({
        x,
        y: height + 8,
        vy: -(height - targetY) / 62, // atteint sa cible en ~1 s
        targetY,
        color: COLORS[(Math.random() * COLORS.length) | 0],
      });
    }

    function explode(x, y, color) {
      const n = 44 + ((Math.random() * 24) | 0);
      for (let i = 0; i < n; i++) {
        const a = (Math.PI * 2 * i) / n;
        const sp = 1.1 + Math.random() * 2.6;
        sparks.push({
          x,
          y,
          vx: Math.cos(a) * sp,
          vy: Math.sin(a) * sp,
          life: 60 + Math.random() * 40,
          max: 100,
          color: Math.random() < 0.75 ? color : COLORS[(Math.random() * COLORS.length) | 0],
        });
      }
    }

    // Arret definitif : dernier effacement, on debranche tout ce qui pourrait
    // relancer la boucle, et `termine` garantit qu'aucune reprise (retour de
    // l'onglet au premier plan, redimensionnement) ne la ressuscite.
    function stopper() {
      termine = true;
      cancelAnimationFrame(raf);
      ctx.clearRect(0, 0, width, height);
      ro.disconnect();
      io.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
    }

    function frame(ts) {
      if (!running || termine) return;

      // Lancer les fusees de la salve, espacees de ~0,7 s, puis ne plus en
      // lancer. `nextLaunch` partant de zero, la premiere part des la premiere
      // image.
      if (tirsRestants > 0 && ts > nextLaunch) {
        launch();
        tirsRestants -= 1;
        nextLaunch = ts + 650 + Math.random() * 500;
      }

      // Salve tiree et ciel vide : c'est fini, pour de bon.
      if (tirsRestants === 0 && rockets.length === 0 && sparks.length === 0) {
        stopper();
        return;
      }

      ctx.clearRect(0, 0, width, height);
      ctx.globalCompositeOperation = blend;

      for (let i = rockets.length - 1; i >= 0; i--) {
        const r = rockets[i];
        r.y += r.vy;
        ctx.globalAlpha = Math.min(1, baseAlpha + 0.3);
        ctx.fillStyle = r.color;
        ctx.beginPath();
        ctx.arc(r.x, r.y, radius + 0.3, 0, Math.PI * 2);
        ctx.fill();
        if (r.y <= r.targetY) {
          explode(r.x, r.y, r.color);
          rockets.splice(i, 1);
        }
      }

      for (let i = sparks.length - 1; i >= 0; i--) {
        const s = sparks[i];
        s.vy += 0.02; // gravite tres douce
        s.vx *= 0.99;
        s.x += s.vx;
        s.y += s.vy;
        s.life -= 1;
        const alpha = Math.max(0, s.life / s.max);
        ctx.globalAlpha = alpha * baseAlpha;
        ctx.fillStyle = s.color;
        ctx.beginPath();
        ctx.arc(s.x, s.y, radius, 0, Math.PI * 2);
        ctx.fill();
        if (s.life <= 0) sparks.splice(i, 1);
      }

      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = "source-over";
      raf = requestAnimationFrame(frame);
    }

    // Deux raisons independantes de suspendre la salve : l'onglet passe en
    // arriere-plan, ou le hero sort du champ avant la fin. Une seule suffit a
    // couper ; il faut les deux pour reprendre - et seulement si la salve n'est
    // pas deja terminee.
    let tabVisible = !document.hidden;
    let onScreen = true;

    function sync() {
      if (termine) return;
      const doitTourner = tabVisible && onScreen;
      if (doitTourner === running) return;
      running = doitTourner;
      if (running) raf = requestAnimationFrame(frame);
      else cancelAnimationFrame(raf);
    }

    function onVisibility() {
      tabVisible = !document.hidden;
      sync();
    }

    const io = new IntersectionObserver(([entry]) => {
      onScreen = entry.isIntersecting;
      sync();
    });
    io.observe(parent);

    document.addEventListener("visibilitychange", onVisibility);
    raf = requestAnimationFrame(frame);

    return () => {
      // Demontage avant la fin de la salve : on coupe sans rejouer `stopper`,
      // qui aurait retouche une toile peut-etre deja detachee.
      running = false;
      termine = true;
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [reduced, theme]);

  if (reduced) return null;
  return <canvas ref={canvasRef} className="fireworks" aria-hidden="true" />;
}
