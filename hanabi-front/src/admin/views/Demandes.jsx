/** Ce que les visiteurs cherchent et que la boutique n'a pas : recherches sans
 *  résultat et demandes au conseiller restées sans objet, regroupées en besoins.
 *  Chargé à part, à l'ouverture du tableau de bord. */
import { useEffect, useState } from "react";

import { api } from "../api.js";
import { num } from "../format.js";
import { Chargement, SousTitre } from "../ui.jsx";

const VISIBLES = 8;

const pluriel = (n, un, plusieurs) => `${num(n)} ${n > 1 ? plusieurs : un}`;

function Origine({ sources }) {
  const parties = [];
  if (sources.recherche) parties.push(pluriel(sources.recherche, "recherche", "recherches"));
  if (sources.conseil) parties.push(`${num(sources.conseil)} via le conseiller`);
  return <span className="dm-origine">{parties.join(" · ")}</span>;
}

export default function Demandes() {
  const [etat, setEtat] = useState({ chargement: true });
  const [tout, setTout] = useState(false);

  useEffect(() => {
    let actif = true;
    api("/admin/demandes")
      .then((r) => actif && setEtat({ donnees: r }))
      .catch((e) => actif && setEtat({ erreur: e.message }));
    return () => {
      actif = false;
    };
  }, []);

  const titre = (
    <SousTitre note="Recherches sans aucun résultat et demandes au conseiller restées sans objet, sur trente jours. De quoi choisir les prochains objets.">
      Ce que tes visiteurs cherchent
    </SousTitre>
  );

  if (etat.chargement) {
    return (
      <>
        {titre}
        <Chargement>Lecture des demandes…</Chargement>
      </>
    );
  }
  if (etat.erreur) {
    return (
      <>
        {titre}
        <p className="adm-err" role="alert">
          {etat.erreur}
        </p>
      </>
    );
  }

  const { besoins, regroupe } = etat.donnees;
  if (!besoins.length) {
    return (
      <>
        {titre}
        <p className="dm-vide">
          Aucune demande sans réponse depuis trente jours : ce qu&apos;on cherche, la boutique
          l&apos;a.
        </p>
      </>
    );
  }

  const max = besoins[0].demandes;
  const affiches = tout ? besoins : besoins.slice(0, VISIBLES);
  return (
    <>
      {titre}
      {!regroupe && (
        <p className="wh-note">
          Regroupement indisponible : chaque recherche est listée telle quelle.
        </p>
      )}
      <ol className="dm-liste">
        {affiches.map((b) => (
          <li key={b.besoin} className="dm-besoin">
            <div className="dm-tete">
              <span className="dm-nom">{b.besoin}</span>
              <span className="dm-compte num">{pluriel(b.demandes, "demande", "demandes")}</span>
            </div>
            <span className="dm-barre" aria-hidden="true">
              <span style={{ inlineSize: `${Math.max(4, (b.demandes / max) * 100)}%` }} />
            </span>
            <div className="dm-pied">
              <Origine sources={b.sources} />
              {b.exemples.length > 0 && (
                <span className="dm-exemples">
                  {b.exemples.map((e) => (
                    <q key={e}>{e}</q>
                  ))}
                </span>
              )}
            </div>
          </li>
        ))}
      </ol>
      {besoins.length > VISIBLES && (
        <button type="button" className="adm-btn sm" onClick={() => setTout((t) => !t)}>
          {tout ? "Voir moins" : `Voir les ${besoins.length} besoins`}
        </button>
      )}
    </>
  );
}
