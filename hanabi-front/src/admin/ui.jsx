/** Petites pieces communes aux ecrans du back-office. */
import { useRef } from "react";
import { ChevronLeft, ChevronRight, Copy } from "lucide-react";

import { copierTexte } from "./api.js";
import { pct, STATUS_LABELS } from "./format.js";

/* Icônes du menu : un tracé de 1,6 sur une grille de 20, angles francs, un seul détail vermillon. */
const ICONES = {
  // Plateau à compartiments, un compartiment laqué
  dashboard: {
    trait: "M2.5 3h15v14h-15zM9 3v14M9 10h8.5",
    accent: "M10.8 4.8h4.9v3.4h-4.9z",
  },
  // La courbe des graphiques du back-office, avec son point final
  analytics: {
    trait: "M2.5 2.5v15h15M5.5 14c1.8 0 2.2-3.5 4.2-3.5s2.5 1.2 4.3-4",
    accent: "M12 6.5a2 2 0 1 0 4 0 2 2 0 1 0-4 0z",
  },
  // Trois couches de données : celle du dessus est la seule que l'écran lit
  warehouse: {
    trait:
      "M3.5 5a6.5 2.3 0 1 0 13 0 6.5 2.3 0 1 0-13 0M3.5 5v10c0 1.27 2.91 2.3 6.5 2.3s6.5-1.03 6.5-2.3V5" +
      "M3.5 10c0 1.27 2.91 2.3 6.5 2.3s6.5-1.03 6.5-2.3",
    accent: "M4.3 5a5.7 1.5 0 1 0 11.4 0 5.7 1.5 0 1 0-11.4 0z",
  },
  // Le courrier qui part, premier sujet de l'écran d'exploitation
  exploitation: {
    trait: "M2.5 4.5h15v11h-15zM5.5 10.5h5M5.5 13h7.5",
    accent: "M12.7 6.3h3v3h-3z",
  },
  // Boîte à objet, nouée d'un cordon vermillon
  products: {
    trait: "M2.5 4h15v4h-15zM3.5 8v9.5h13V8",
    accent: "M9 3.2h2v15.1H9z",
  },
  // Étiquette et son œillet
  promos: {
    trait: "M10.3 2.5h7.2v7.2l-7.8 7.8-7.2-7.2z",
    accent: "M12.4 6a1.6 1.6 0 1 0 3.2 0 1.6 1.6 0 1 0-3.2 0z",
  },
  // Le reçu frappé d'un sceau, comme sur la boutique
  orders: {
    trait: "M4.5 2.5h11v15l-2.2-1.35-2.2 1.35-2.2-1.35-2.2 1.35-2.2-1.35zM7.3 6.5h5.4M7.3 9.5h3",
    accent: "M11.2 11.4h2.8v2.8h-2.8z",
  },
  // Le buste en kimono du compte client, et un second client derrière
  users: {
    trait:
      "M2.5 17.5v-1.6c0-2.5 2.2-3.9 5-3.9s5 1.4 5 3.9v1.6zM8.9 12.2l-2.6 5.3M6.1 12.2l1.4 2.85" +
      "M11.6 5.4a2.3 2.3 0 1 0 4.6 0 2.3 2.3 0 1 0-4.6 0M14.6 11.3c1.8.5 2.9 1.8 2.9 3.8v2.4",
    accent: "M4.7 6.3a2.8 2.8 0 1 0 5.6 0 2.8 2.8 0 1 0-5.6 0z",
  },
  // Le torii du menu de la boutique
  retour: {
    trait: "M2.9 4.3c2.5.75 11.7.75 14.2 0M4.6 7.7h10.8M6.7 5.3v12.2M13.3 5.3v12.2",
    accent: "M8.7 7.7h2.6v2H8.7z",
  },
  quitter: {
    trait: "M5.5 5.2a7 7 0 1 0 9 0",
    accent: "M9.2 2.5h1.6v8H9.2z",
  },
  // Le disque partagé de la boutique : le demi-disque change de côté avec le thème
  sombre: {
    trait: "M10 3.2a6.8 6.8 0 1 0 0 13.6 6.8 6.8 0 1 0 0-13.6",
    accent: "M10 4.8a5.2 5.2 0 0 1 0 10.4z",
  },
  clair: {
    trait: "M10 3.2a6.8 6.8 0 1 0 0 13.6 6.8 6.8 0 1 0 0-13.6",
    accent: "M10 4.8a5.2 5.2 0 0 0 0 10.4z",
  },
};

export function Ico({ nom }) {
  const { trait, accent } = ICONES[nom];
  return (
    <svg
      className="adm-nav-ic"
      viewBox="0 0 20 20"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="square"
      strokeLinejoin="miter"
      aria-hidden="true"
    >
      <path d={trait} />
      <path d={accent} fill="var(--accent)" stroke="none" />
    </svg>
  );
}

/** Variation d'une periode a l'autre. `null` : periode precedente vide, donc
 *  aucune comparaison possible ; ce n'est pas zero. */
export function Delta({ value, inverse = false }) {
  if (value == null) return <span className="delta delta-none">nouveau</span>;
  const bon = inverse ? value <= 0 : value >= 0;
  return (
    <span className={"delta " + (bon ? "delta-up" : "delta-down")}>
      <span aria-hidden="true">{value > 0 ? "▲" : value < 0 ? "▼" : "="}</span>
      {value > 0 ? "+" : ""}
      {pct(value)}
    </span>
  );
}

export function StatusBadge({ status }) {
  return (
    <span className="status-badge" data-status={status}>
      {STATUS_LABELS[status] || status}
    </span>
  );
}

export function Chargement({ children }) {
  return (
    <div className="adm-loading" role="status">
      <span className="adm-spin" aria-hidden="true" /> {children}
    </div>
  );
}

export function Pager({ page, pages, onPage, libelle }) {
  return (
    <nav className="adm-pager" aria-label={libelle}>
      <button
        className="adm-btn sm"
        disabled={page === 0}
        onClick={() => onPage(page - 1)}
        aria-label="Page précédente"
      >
        <ChevronLeft size={16} aria-hidden="true" />
      </button>
      <span className="num">
        {page + 1} / {pages}
      </span>
      <button
        className="adm-btn sm"
        disabled={page + 1 >= pages}
        onClick={() => onPage(page + 1)}
        aria-label="Page suivante"
      >
        <ChevronRight size={16} aria-hidden="true" />
      </button>
    </nav>
  );
}

export function SousTitre({ children, note }) {
  return (
    <div className="adm-sub">
      <h3>{children}</h3>
      {note && <p className="adm-sub-note">{note}</p>}
    </div>
  );
}

/** Bloc de code avec son bouton de copie. */
export function BlocCode({ titre, texte, flash }) {
  const bloc = useRef(null);
  return (
    <div className="wh-code">
      <div className="wh-code-head">
        <span>{titre}</span>
        <button className="adm-btn sm on-lacquer" onClick={() => copierTexte(texte, flash, bloc)}>
          <Copy size={14} aria-hidden="true" /> Copier
        </button>
      </div>
      <pre className="wh-sql" ref={bloc}>
        {texte}
      </pre>
    </div>
  );
}
