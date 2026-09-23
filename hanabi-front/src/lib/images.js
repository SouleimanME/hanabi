/** Photos servies par un CDN qui redimensionne à la volée (Unsplash) : le
 *  navigateur prend la largeur qu'il affiche, une vignette de 64 px ne décode
 *  plus une photo de 1 200 px. */

// Les deux dernières servent au zoom de la fiche : agrandie, la photo reste nette
export const LARGEURS = [160, 320, 480, 720, 960, 1200, 1800, 2400];

/** `srcset` d'une photo Unsplash, proportions conservées ; `null` pour une autre source. */
export function sourcesAdaptees(url) {
  let u;
  try {
    u = new URL(url);
  } catch {
    return null;
  }
  if (u.hostname !== "images.unsplash.com") return null;
  const largeur = Number(u.searchParams.get("w")) || 1200;
  const hauteur = Number(u.searchParams.get("h"));
  return LARGEURS.map((w) => {
    u.searchParams.set("w", String(w));
    if (hauteur) u.searchParams.set("h", String(Math.round((hauteur * w) / largeur)));
    return `${u.toString()} ${w}w`;
  }).join(", ");
}
