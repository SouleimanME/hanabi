/** Champ d'adresse qui propose des adresses complètes au fil de la frappe
 *  (motif « combobox » de l'ARIA APG) : flèches pour parcourir, Entrée pour
 *  choisir, Échap pour fermer. La saisie libre reste toujours possible. */
import { useEffect, useId, useRef, useState } from "react";
import { useT } from "../../i18n/context.jsx";
import { suggererAdresses } from "../../lib/adresses.js";

// Une requête par pause de frappe, pas une par lettre
const ATTENTE_MS = 200;

export function ChampAdresse({ id, value, onChange, onChoisir, ...attributs }) {
  const t = useT();
  const liste = useId();
  const [options, setOptions] = useState([]);
  const [ouvert, setOuvert] = useState(false);
  const [actif, setActif] = useState(-1);
  const minuteur = useRef(0);
  const requete = useRef(null);

  useEffect(
    () => () => {
      clearTimeout(minuteur.current);
      requete.current?.abort();
    },
    [],
  );

  const proposer = (saisie) => {
    clearTimeout(minuteur.current);
    requete.current?.abort();
    minuteur.current = setTimeout(async () => {
      const controle = new AbortController();
      requete.current = controle;
      try {
        const trouvees = await suggererAdresses(saisie, controle.signal);
        setOptions(trouvees);
        setActif(-1);
        setOuvert(trouvees.length > 0 && document.activeElement?.id === id);
      } catch {
        // Réseau coupé ou requête remplacée : le champ reste un champ ordinaire
      }
    }, ATTENTE_MS);
  };

  const choisir = (option) => {
    onChoisir(option);
    setOuvert(false);
    setOptions([]);
    setActif(-1);
  };

  const surTouche = (e) => {
    if (!ouvert) {
      if (e.key === "ArrowDown" && options.length) {
        e.preventDefault();
        setOuvert(true);
        setActif(0);
      }
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActif((i) => (i + 1) % options.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActif((i) => (i <= 0 ? options.length - 1 : i - 1));
    } else if (e.key === "Enter" && actif >= 0) {
      // Choisir une adresse n'envoie pas le formulaire
      e.preventDefault();
      choisir(options[actif]);
    } else if (e.key === "Escape") {
      e.preventDefault();
      setOuvert(false);
    }
  };

  return (
    <div className="adresse">
      <input
        id={id}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={ouvert}
        aria-controls={liste}
        aria-activedescendant={ouvert && actif >= 0 ? `${liste}-${actif}` : undefined}
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          proposer(e.target.value);
        }}
        onKeyDown={surTouche}
        onBlur={() => setOuvert(false)}
        autoComplete="address-line1"
        {...attributs}
      />
      <ul
        className="adresse-liste"
        id={liste}
        role="listbox"
        aria-label={t("addrList")}
        hidden={!ouvert}
      >
        {options.map((o, i) => (
          <li
            key={o.id}
            id={`${liste}-${i}`}
            role="option"
            aria-selected={i === actif}
            // Garder le focus dans le champ : sans cela, il se ferme avant le clic
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => choisir(o)}
          >
            <span className="adresse-rue">{o.adresse}</span>
            <span className="adresse-ville">
              {o.cp} {o.ville}
            </span>
          </li>
        ))}
      </ul>
      <span className="sr-only" aria-live="polite">
        {ouvert ? t("addrFound", { n: options.length }) : ""}
      </span>
    </div>
  );
}
