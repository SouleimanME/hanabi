/** Marque d'acceptation d'un réseau de cartes, dans ses couleurs officielles
 *  (datatrans/payment-logos, CC BY-SA 4.0, fichiers inchangés). */
const FICHIERS = { visa: "visa", mastercard: "mastercard", amex: "american-express" };

export const RESEAUX_ACCEPTES = Object.keys(FICHIERS);

export function LogoReseau({ reseau, nom = "" }) {
  const fichier = FICHIERS[reseau];
  if (!fichier) return null;
  return (
    <img
      className="logo-reseau"
      src={`/cartes/${fichier}.svg`}
      alt={nom}
      width="30"
      height="20"
      decoding="async"
    />
  );
}
