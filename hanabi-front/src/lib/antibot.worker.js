/** Recherche du nonce anti-robots, hors du fil principal.
 *
 * Ce fichier s'execute dans un Web Worker : il a son propre fil, sa propre
 * boucle d'evenements, et ne partage rien avec la page. Le calcul peut donc
 * tourner a pleine vitesse sans jamais retarder une image, une frappe au
 * clavier ou un defilement.
 *
 * C'est ce qui manquait a la version precedente. Elle tournait dans la page et
 * tentait de menager le navigateur en rendant la main toutes les deux mille
 * tentatives. Mais chaque tentative faisait `await crypto.subtle.digest(...)`,
 * et une promesse deja resolue ne rend la main qu'a la file de MICROTACHES -
 * laquelle est videe entierement avant que le navigateur ne puisse peindre. Le
 * fil principal restait donc bloque par blocs de deux mille hachages, soit des
 * dizaines de millisecondes d'affilee, plusieurs fois de suite. A soixante
 * images par seconde, on dispose de seize millisecondes : chaque bloc en
 * sacrifiait plusieurs.
 *
 * Le probleme se voyait partout parce que la preuve est demandee partout : a
 * l'ouverture de la page d'accueil, a l'ouverture du formulaire de connexion,
 * deux fois sur une fiche produit - et une nouvelle preuve est relancee en
 * arriere-plan apres chaque usage.
 *
 * Ici, plus besoin de menagement : la boucle est serree, sans respiration, ce
 * qui la rend au passage nettement plus rapide.
 */

/** Compte les bits a zero en tete d'une empreinte. */
function leadingZeroBits(bytes) {
  let bits = 0;
  for (const byte of bytes) {
    if (byte === 0) {
      bits += 8;
      continue;
    }
    // 8 moins la position du bit de poids fort a 1.
    bits += 8 - byte.toString(2).length;
    break;
  }
  return bits;
}

self.onmessage = async (event) => {
  const { salt, difficulty, id } = event.data;
  const encodeur = new TextEncoder();

  try {
    let nonce = 0;
    for (;;) {
      const empreinte = new Uint8Array(
        await crypto.subtle.digest("SHA-256", encodeur.encode(`${salt}${nonce}`)),
      );
      if (leadingZeroBits(empreinte) >= difficulty) {
        self.postMessage({ id, nonce: String(nonce) });
        return;
      }
      nonce++;
    }
  } catch (erreur) {
    self.postMessage({ id, erreur: String(erreur) });
  }
};
