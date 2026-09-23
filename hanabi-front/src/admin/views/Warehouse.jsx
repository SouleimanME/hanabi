/** Entrepôt : tables d'agrégats construites par dbt, et la requête qui les lit. */
import { useEffect, useRef, useState } from "react";
import { Copy, Play, RotateCcw } from "lucide-react";

import { api, copierTexte } from "../api.js";
import { anciennete, eur, fmtDate, num, pct } from "../format.js";
import { BlocCode, Chargement, Pager } from "../ui.jsx";

const TAILLE_PAGE = 25;
const FORMATS_NUMERIQUES = ["euro", "pourcent", "entier", "decimal", "identifiant"];
// Construction quotidienne : au-delà, la dernière a échoué
const PEREMPTION_HEURES = 26;

/** Cellule selon le format annoncé par l'API. null veut dire « non mesurable ». */
function cellule(valeur, format) {
  if (valeur === null || valeur === undefined) return "-";
  switch (format) {
    case "euro":
      return eur(valeur);
    case "pourcent":
      return pct(valeur);
    case "entier":
      return num(valeur);
    case "identifiant":
      return String(valeur);
    case "decimal":
      return Number(valeur).toLocaleString("fr-FR", { maximumFractionDigits: 3 });
    case "booleen":
      return valeur ? "oui" : "non";
    case "date":
      return fmtDate(valeur);
    default:
      return String(valeur);
  }
}

function TableEntrepot({ colonnes, lignes, tri, sens, onTrier, legende }) {
  return (
    <div className="wh-cadre">
      <table className="adm-table wh-table">
        {legende && <caption className="sr-only">{legende}</caption>}
        <thead>
          <tr>
            {colonnes.map((colonne) => {
              const numerique = FORMATS_NUMERIQUES.includes(colonne.format);
              const actif = tri === colonne.nom;
              return (
                <th
                  key={colonne.nom}
                  scope="col"
                  className={numerique ? "num" : undefined}
                  aria-sort={actif ? (sens === "desc" ? "descending" : "ascending") : undefined}
                >
                  {onTrier ? (
                    <button
                      className="th-sort"
                      title={`${colonne.nom} · ${colonne.format}`}
                      onClick={() => onTrier(colonne.nom)}
                    >
                      {colonne.libelle}
                      {actif && <span aria-hidden="true">{sens === "desc" ? " ↓" : " ↑"}</span>}
                    </button>
                  ) : (
                    <span title={`${colonne.nom} · ${colonne.format}`}>{colonne.libelle}</span>
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {lignes.map((ligne, i) => (
            <tr key={i}>
              {ligne.map((valeur, j) => (
                <td
                  key={j}
                  className={FORMATS_NUMERIQUES.includes(colonnes[j].format) ? "num" : undefined}
                >
                  {cellule(valeur, colonnes[j].format)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Console en lecture seule ; les garde-fous et les messages de refus viennent du serveur. */
function ConsoleSql({ sqlInitial, aide, flash, onResultat }) {
  const [sql, setSql] = useState(sqlInitial);
  const [resultat, setResultat] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [busy, setBusy] = useState(false);
  const [aideOuverte, setAideOuverte] = useState(false);
  const [modifiee, setModifiee] = useState(false);
  const champ = useRef(null);

  // Changer de table remplace la requete, sauf si l'on a commence a ecrire
  useEffect(() => {
    if (!modifiee) setSql(sqlInitial);
  }, [sqlInitial, modifiee]);

  async function executer() {
    setBusy(true);
    setErreur(null);
    try {
      const res = await api("/admin/warehouse/sql", { method: "POST", body: { sql, limite: 100 } });
      setResultat(res);
      onResultat?.(res);
    } catch (e) {
      setErreur(e.message);
      setResultat(null);
      onResultat?.(null);
    } finally {
      setBusy(false);
    }
  }

  function reinitialiser() {
    setSql(sqlInitial);
    setModifiee(false);
    setResultat(null);
    setErreur(null);
    onResultat?.(null);
  }

  const lignes = sql.split("\n").length;

  return (
    <section className="wh-console" aria-labelledby="console-titre">
      <div className="wh-code-head">
        <span id="console-titre">Requête</span>
        <div className="wh-console-actions">
          <button
            className="adm-btn sm on-lacquer"
            onClick={() => setAideOuverte((o) => !o)}
            aria-expanded={aideOuverte}
          >
            {aideOuverte ? "Masquer l'aide" : "Aide et exemples"}
          </button>
          {modifiee && (
            <button className="adm-btn sm on-lacquer" onClick={reinitialiser}>
              <RotateCcw size={14} aria-hidden="true" /> Réinitialiser
            </button>
          )}
          <button className="adm-btn sm on-lacquer" onClick={() => copierTexte(sql, flash, champ)}>
            <Copy size={14} aria-hidden="true" /> Copier
          </button>
          <button className="adm-btn sm primary" onClick={executer} disabled={busy}>
            <Play size={14} aria-hidden="true" /> {busy ? "Exécution…" : "Exécuter"}
          </button>
        </div>
      </div>

      <div className="wh-editeur">
        <span className="wh-gouttiere" aria-hidden="true">
          {Array.from({ length: Math.max(lignes, 5) }, (_, i) => (
            <span key={i}>{i + 1}</span>
          ))}
        </span>
        <textarea
          ref={champ}
          className="wh-sql wh-saisie"
          value={sql}
          spellCheck={false}
          rows={Math.min(16, Math.max(5, lignes + 1))}
          onChange={(e) => {
            setSql(e.target.value);
            setModifiee(true);
          }}
          onKeyDown={(e) => {
            // Ctrl+Entree execute ; Entree reste un retour a la ligne
            if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
              e.preventDefault();
              executer();
            }
          }}
          aria-label="Requête SQL"
          aria-describedby="console-regles"
        />
      </div>

      <div className="wh-console-pied" id="console-regles">
        <span>
          <kbd>Ctrl</kbd> + <kbd>Entrée</kbd> pour exécuter
        </span>
        {aide && (
          <span>
            Lecture seule · schémas {aide.schemas.join(", ")} · {aide.delai_max_s} s maximum
          </span>
        )}
      </div>

      {aideOuverte && aide && (
        <div className="wh-aide">
          <ul className="wh-regles">
            {aide.regles.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          <div className="wh-exemples">
            {aide.exemples.map((ex) => (
              <button
                key={ex.titre}
                className="adm-btn sm on-lacquer"
                onClick={() => {
                  setSql(ex.sql);
                  setModifiee(true);
                  setErreur(null);
                  champ.current?.focus();
                }}
              >
                {ex.titre}
              </button>
            ))}
          </div>
        </div>
      )}

      {erreur && (
        <div className="adm-err wh-erreur" role="alert">
          {erreur}
        </div>
      )}

      {resultat && (
        <div className="wh-resultat">
          <p className="adm-count" aria-live="polite">
            {num(resultat.total)} ligne{resultat.total > 1 ? "s" : ""}
            {resultat.tronque && " (tronqué)"}
            {resultat.tables_lues.length > 0 && (
              <>
                {" · "}
                <span className="code">{resultat.tables_lues.join(", ")}</span>
              </>
            )}
          </p>
          {resultat.lignes.length === 0 ? (
            <p className="wh-note">Aucune ligne ne satisfait cette requête.</p>
          ) : (
            <TableEntrepot
              colonnes={resultat.colonnes}
              lignes={resultat.lignes}
              legende="Résultat de la requête"
            />
          )}
        </div>
      )}
    </section>
  );
}

function Couches({ couches }) {
  return (
    <ol className="wh-couches" aria-label="Couches de l'entrepôt, de la source aux agrégats">
      {couches.map((couche, rang) => (
        <li key={couche.cle} className={"wh-couche wh-" + couche.cle}>
          <div className="wh-couche-tete">
            <span className="code">{String(rang + 1).padStart(2, "0")}</span>
            <h3 className="wh-couche-titre">{couche.titre}</h3>
            <span
              className="wh-couche-compte num"
              title="Modèles présents en base sur modèles déclarés"
            >
              {couche.presents.length}/{couche.modeles.length}
            </span>
          </div>
          <p className="wh-couche-resume">{couche.resume}</p>
          <ul className="wh-chips">
            {couche.modeles.map((modele) => {
              const present = couche.presents.includes(modele);
              return (
                <li
                  key={modele}
                  className={"wh-chip" + (present ? "" : " absent")}
                  title={
                    present
                      ? `${couche.cle}.${modele}`
                      : "Déclaré mais absent de la base : reconstruis l'entrepôt."
                  }
                >
                  {modele}
                  {!present && <span className="sr-only"> (absent)</span>}
                </li>
              );
            })}
          </ul>
          <p className="wh-couche-pied">Matérialisées en {couche.materialisation}</p>
        </li>
      ))}
    </ol>
  );
}

const ETATS = { reussi: "Réussi", alerte: "Alerte", echec: "Échec" };

/** Un contrôle raté n'est un échec que s'il est bloquant ; sinon c'est une alerte. */
function etatControle(controle) {
  if (controle.reussi) return "reussi";
  return controle.severite === "erreur" ? "echec" : "alerte";
}

/** Contrôles de volume et de fraîcheur, consignés par Dagster dans `controles.journal`. */
function Controles({ controles }) {
  return (
    <section className="wh-controles" aria-labelledby="controles-titre">
      <div className="wh-controles-tete">
        <h2 id="controles-titre">Contrôles</h2>
        <p>Volume et fraîcheur, vérifiés par Dagster après chaque construction.</p>
      </div>
      {controles.length === 0 ? (
        <p className="wh-note">
          Aucun contrôle consigné : le journal s&apos;écrit à la première exécution Dagster.
        </p>
      ) : (
        <ul className="wh-controles-liste">
          {controles.map((controle) => {
            const etat = etatControle(controle);
            return (
              <li key={controle.controle} className="wh-controle" data-etat={etat}>
                <span className="status-badge" data-status={etat}>
                  {ETATS[etat]}
                </span>
                <strong className="wh-controle-titre">{controle.titre}</strong>
                <span className="wh-controle-message">{controle.message}</span>
                <span className="wh-controle-attendu">
                  {controle.famille === "volume" ? "Volume" : "Fraîcheur"} · attendu :{" "}
                  {controle.attendu}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

export function Warehouse({ flash }) {
  const [etat, setEtat] = useState(null);
  const [cle, setCle] = useState(null);
  const [vue, setVue] = useState(null);
  const [tri, setTri] = useState(null);
  const [sens, setSens] = useState("desc");
  const [page, setPage] = useState(0);
  const [busy, setBusy] = useState(false);
  const [aide, setAide] = useState(null);
  const [resultatSql, setResultatSql] = useState(null);

  useEffect(() => {
    api("/admin/warehouse")
      .then((res) => {
        setEtat(res);
        const premier = res.marts.find((m) => m.disponible);
        if (premier) setCle(premier.cle);
      })
      .catch((e) => flash(e.message, "err"));
    // Les regles de la console ne changent pas ; sans elles, la console reste utilisable
    api("/admin/warehouse/sql/aide")
      .then(setAide)
      .catch(() => setAide(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Une autre table : tri, page et resultat libre repartent de zero
  useEffect(() => {
    setTri(null);
    setSens("desc");
    setPage(0);
    setResultatSql(null);
  }, [cle]);

  useEffect(() => {
    if (!cle) return undefined;
    let annule = false;
    setBusy(true);
    const params = new URLSearchParams({
      limite: String(TAILLE_PAGE),
      decalage: String(page * TAILLE_PAGE),
      sens,
    });
    if (tri) params.set("tri", tri);
    api(`/admin/warehouse/marts/${cle}?${params}`)
      .then((res) => !annule && setVue(res))
      .catch((e) => !annule && flash(e.message, "err"))
      .finally(() => !annule && setBusy(false));
    return () => {
      annule = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cle, tri, sens, page]);

  if (!etat) return <Chargement>Inspection de l&apos;entrepôt</Chargement>;

  if (!etat.disponible) {
    return (
      <div className="wh">
        <section className="wh-absent" aria-labelledby="wh-absent-titre">
          <h2 id="wh-absent-titre">L&apos;entrepôt n&apos;est pas construit sur cette base</h2>
          <p>
            {etat.raison === "moteur"
              ? "La base courante n'est pas PostgreSQL. Les modèles emploient date_trunc, generate_series et des fonctions de fenêtrage : ils se construisent sur PostgreSQL, en local dans un conteneur ou sur Neon."
              : "Les schémas bronze, silver et gold sont absents de cette base. Ils se créent en une commande."}
          </p>
          <BlocCode titre="À lancer" texte="cd hanabi-dwh && python dwh.py build" flash={flash} />
          <p className="wh-note">
            La construction lit les tables de l&apos;application et n&apos;écrit que dans ses
            propres schémas.
          </p>
        </section>
        <Couches couches={etat.couches} />
      </div>
    );
  }

  const mart = etat.marts.find((m) => m.cle === cle);
  const pages = Math.max(1, Math.ceil((vue?.total || 0) / TAILLE_PAGE));
  const heures = etat.construit_le
    ? (Date.now() - new Date(etat.construit_le).getTime()) / 3600000
    : null;
  const perime = heures == null || heures > PEREMPTION_HEURES;

  return (
    <div className="wh">
      <Couches couches={etat.couches} />

      <p className="wh-fraicheur" data-perime={perime || undefined}>
        <strong>Construit {anciennete(etat.construit_le)}</strong>
        {etat.construit_le && (
          <time dateTime={etat.construit_le} className="num">
            {new Date(etat.construit_le).toLocaleString("fr-FR")}
          </time>
        )}
        <span>
          {perime
            ? "La construction quotidienne n'a pas tourné : ces chiffres datent."
            : "Chiffres de la dernière construction, pas de l'instant."}
        </span>
      </p>

      <Controles controles={etat.controles || []} />

      <div className="adm-subnav">
        <div className="adm-segments wh-marts" role="group" aria-label="Tables d'agrégats">
          {etat.marts.map((m) => (
            <button
              key={m.cle}
              className="adm-subnav-btn"
              aria-pressed={cle === m.cle}
              disabled={!m.disponible}
              onClick={() => setCle(m.cle)}
            >
              {m.titre}
              <span className="wh-compte num">{num(m.lignes)}</span>
            </button>
          ))}
        </div>
        {busy && <span className="adm-spin" role="status" aria-label="Lecture en cours" />}
      </div>

      {mart && (
        <div className="wh-mart">
          <h2 className="wh-mart-titre">{mart.titre}</h2>
          <p className="wh-question">{mart.question}</p>
        </div>
      )}

      {vue && vue.cle === cle && (
        <>
          <ConsoleSql sqlInitial={vue.sql} aide={aide} flash={flash} onResultat={setResultatSql} />

          {/* Un résultat libre remplace la table */}
          {!resultatSql && (
            <div>
              <div className="adm-toolbar">
                <span className="adm-count">
                  {num(vue.total)} ligne{vue.total > 1 ? "s" : ""} dans{" "}
                  <span className="code">{vue.table}</span>
                </span>
                <div className="adm-toolbar-end">
                  <Pager page={page} pages={pages} onPage={setPage} libelle="Pages de la table" />
                </div>
              </div>
              <TableEntrepot
                colonnes={vue.colonnes}
                lignes={vue.lignes}
                tri={tri}
                sens={sens}
                legende={mart?.titre}
                onTrier={(nom) => {
                  if (tri === nom) setSens(sens === "desc" ? "asc" : "desc");
                  else {
                    setTri(nom);
                    setSens("desc");
                  }
                  setPage(0);
                }}
              />
              {vue.lignes.length === 0 && (
                <p className="wh-note">
                  Table construite mais vide : aucune ligne ne satisfait les critères du modèle.
                </p>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
