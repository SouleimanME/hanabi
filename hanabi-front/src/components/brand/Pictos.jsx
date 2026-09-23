/** Pictogrammes maison : contour en laque (`currentColor`), détail en vermillon (`--accent`). */

function Picto({ taille = 20, className, children }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={taille}
      height={taille}
      className={"picto" + (className ? ` ${className}` : "")}
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

/** Anneau et demi-disque : pivote d'un demi-tour selon le thème. */
export function PictoTheme(props) {
  return (
    <Picto {...props}>
      <circle cx="12" cy="12" r="8.25" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d="M12 5.4a6.6 6.6 0 0 1 0 13.2z" fill="var(--accent)" />
    </Picto>
  );
}

export function PictoFavori({ plein = false, ...props }) {
  return (
    <Picto {...props}>
      <path
        d="M12 20 4.9 12.6a4.4 4.4 0 0 1 7.1-5.1 4.4 4.4 0 0 1 7.1 5.1Z"
        fill={plein ? "var(--accent)" : "none"}
        stroke={plein ? "var(--accent)" : "currentColor"}
        strokeWidth="1.6"
      />
    </Picto>
  );
}

/** Buste en kimono, col croisé à gauche sur droite, tête en disque vermillon. */
export function PictoCompte(props) {
  return (
    <Picto {...props}>
      <circle cx="12" cy="7.3" r="4.1" fill="var(--accent)" />
      <path
        d="M5.6 20.25v-2.4c0-2.8 2.7-4.3 6.4-4.3s6.4 1.5 6.4 4.3v2.4ZM14.1 13.75 9.55 20.25M9.9 13.75 12 16.75"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
      />
    </Picto>
  );
}

/** Furoshiki : baluchon et nœud vermillon. */
export function PictoPanier(props) {
  return (
    <Picto {...props}>
      <path
        d="M4.8 11.6h14.4v5.2a3.4 3.4 0 0 1-3.4 3.4H8.2a3.4 3.4 0 0 1-3.4-3.4Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path d="M12 11.6 7.4 5.6l4 1.3ZM12 11.6l4.6-6-4 1.3Z" fill="var(--accent)" />
    </Picto>
  );
}

/** Signet des articles gardés pour plus tard. */
export function PictoGarde(props) {
  return (
    <Picto {...props}>
      <path d="M7 3.75h10v16.5l-5-3.9-5 3.9Z" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d="M9.6 3.75h4.8v4.6L12 6.9l-2.4 1.45Z" fill="var(--accent)" />
    </Picto>
  );
}

/** Reçu frappé d'un sceau vermillon. */
export function PictoCommandes(props) {
  return (
    <Picto {...props}>
      <path
        d="M6.25 3.75h11.5v16.5l-2.3-1.4-2.3 1.4-2.3-1.4-2.3 1.4-2.3-1.4ZM9 8h6M9 11.4h3.6"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path d="M13.2 13.4h3v3h-3Z" fill="var(--accent)" />
    </Picto>
  );
}

export function PictoMenu(props) {
  return (
    <Picto {...props}>
      <path d="M4 8.5h16M4 15.5h10" stroke="currentColor" strokeWidth="1.6" />
    </Picto>
  );
}

export function PictoLoupe(props) {
  return (
    <Picto {...props}>
      <g fill="none" stroke="currentColor" strokeWidth="1.6">
        <circle cx="10.5" cy="10.5" r="6.25" />
        <path d="m15.2 15.2 5 5" />
      </g>
    </Picto>
  );
}

/** Torii : retour à la boutique. */
export function PictoBoutique(props) {
  return (
    <Picto {...props}>
      <path
        d="M3.5 5.2c3 .9 14 .9 17 0M5.5 9.2h13M8 6.3v14M16 6.3v14"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path d="M10.4 9.2h3.2v2.4h-3.2Z" fill="var(--accent)" />
    </Picto>
  );
}
