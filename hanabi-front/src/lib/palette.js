/** Palette des etincelles, lue dans les jetons du theme actif.
 *
 * Les feux d'artifice etaient peints avec une palette figee, choisie pour le
 * fond sombre : elle contenait la couleur du papier, donc invisible sur le
 * theme clair. Lire les jetons CSS resout le probleme a la racine - `--accent`,
 * `--gold`, `--indigo` et `--ink` s'inversent tous correctement d'un theme a
 * l'autre, si bien que la palette suit le theme sans condition a maintenir.
 *
 * Effet de bord utile : retoucher la palette dans `tokens.css` retouche aussi
 * les etincelles.
 */

/** Repli si le DOM n'est pas encore pret ou si un jeton manque. */
const FALLBACK = ["#e0382a", "#b98a2e", "#1b3a5b", "#16140f"];

const TOKENS = ["--accent", "--gold", "--indigo", "--ink"];

/** Le theme sombre est-il actif ? */
export function isDarkTheme() {
  return document.querySelector(".root")?.classList.contains("dark") ?? false;
}

/**
 * Renvoie les couleurs d'etincelles du theme courant.
 *
 * A appeler au declenchement d'une animation, pas a chaque image : lire un
 * style calcule force le navigateur a resoudre la mise en page.
 *
 * @returns {string[]}
 */
export function sparkPalette() {
  const root = document.querySelector(".root");
  if (!root) return FALLBACK;
  const styles = getComputedStyle(root);
  const colors = TOKENS.map((token) => styles.getPropertyValue(token).trim()).filter(Boolean);
  return colors.length > 0 ? colors : FALLBACK;
}

/**
 * Reglages de rendu adaptes au fond.
 *
 * Sur fond sombre, le mode additif (`lighter`) fait rougeoyer les etincelles
 * qui se superposent - c'est ce qui donne l'impression de braise. Sur fond
 * clair, ce meme mode est inoperant : ajouter de la lumiere a du blanc ne
 * produit rien. On repasse donc en trace opaque, plus dense et legerement plus
 * gros, qui se lit comme un pigment projete sur du papier.
 *
 * @returns {{blend: GlobalCompositeOperation, alpha: number, radius: number}}
 */
export function sparkRender() {
  return isDarkTheme()
    ? { blend: "lighter", alpha: 0.55, radius: 1.5 }
    : { blend: "source-over", alpha: 0.95, radius: 1.9 };
}
