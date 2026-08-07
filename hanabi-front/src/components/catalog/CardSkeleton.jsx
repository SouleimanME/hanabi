/** Squelette d'une carte produit, affiche pendant le premier chargement.
 *
 * Un squelette qui reprend exactement la silhouette de la vraie carte (meme
 * proportion de visuel, meme hauteur de lignes) evite le sursaut de mise en
 * page a l'arrivee des donnees : rien ne bouge, le gris devient du contenu.
 *
 * `aria-hidden` : c'est une attente, pas une information. Les lecteurs d'ecran
 * l'ignorent et s'appuient sur la region live de la grille.
 */
export function CardSkeleton({ index = 0 }) {
  return (
    <div className="skel-card" aria-hidden="true" style={{ animationDelay: `${index * 90}ms` }}>
      <div className="skel-art skel-shine" />
      <div className="skel-body">
        <div className="skel-line skel-shine" style={{ width: "38%" }} />
        <div className="skel-line lg skel-shine" style={{ width: "72%" }} />
        <div className="skel-line skel-shine" style={{ width: "52%" }} />
        <div className="skel-line skel-shine" style={{ width: "90%" }} />
        <div className="skel-foot">
          <div className="skel-line skel-shine" style={{ width: "40%" }} />
          <div className="skel-pill skel-shine" />
        </div>
      </div>
    </div>
  );
}
