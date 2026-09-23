/** Case du plateau en attente de donnees : meme silhouette que la vraie, pour
 *  que rien ne saute a l'arrivee du catalogue. */
export function CardSkeleton() {
  return (
    <li className="case case-skel" aria-hidden="true">
      <div className="case-art" />
      <div className="case-body">
        <span className="skel-line" style={{ inlineSize: "34%" }} />
        <span className="skel-line skel-lg" style={{ inlineSize: "72%" }} />
        <span className="skel-line" style={{ inlineSize: "28%" }} />
      </div>
    </li>
  );
}
