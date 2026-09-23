/** Commandes : recherche et pages côté serveur, détail de livraison, statut suivant, export CSV. */
import { Fragment, useCallback, useEffect, useState } from "react";
import { ChevronDown, Download } from "lucide-react";

import { api, download } from "../api.js";
import { eur, fmtDate, LECTURE_SEULE, STATUS_LABELS } from "../format.js";
import { Pager, StatusBadge } from "../ui.jsx";

const PAGE = 40;

export function Orders({ flash, readonly }) {
  const [search, setSearch] = useState("");
  const [statut, setStatut] = useState("");
  const [page, setPage] = useState(0);
  const [donnees, setDonnees] = useState(null);
  const [ouverte, setOuverte] = useState(null);

  const charger = useCallback(
    async (q, s, p) => {
      try {
        const query = new URLSearchParams({ limit: PAGE, offset: p * PAGE });
        if (q.trim()) query.set("q", q.trim());
        if (s) query.set("statut", s);
        setDonnees(await api(`/admin/orders?${query}`));
      } catch (e) {
        flash(e.message, "err");
      }
    },
    [flash],
  );

  // Saisie temporisée : une requête par caractère saturerait l'API
  useEffect(() => {
    const minuteur = setTimeout(() => charger(search, statut, page), 250);
    return () => clearTimeout(minuteur);
  }, [search, statut, page, charger]);

  const changerStatut = async (number, suivant) => {
    try {
      const res = await api(`/admin/orders/${number}/status?status=${suivant}`, {
        method: "PATCH",
      });
      flash(
        res.remis_en_stock
          ? `${number} : ${STATUS_LABELS[suivant]}, ${res.remis_en_stock} article${res.remis_en_stock > 1 ? "s" : ""} remis en stock`
          : `${number} : ${STATUS_LABELS[suivant]}`,
      );
      charger(search, statut, page);
    } catch (e) {
      flash(e.message, "err");
    }
  };

  const total = donnees?.total ?? 0;
  const lignes = donnees?.items ?? [];
  const pages = Math.max(1, Math.ceil(total / PAGE));

  return (
    <div>
      {donnees?.masque && (
        <p className="adm-warn">
          Compte de démonstration : adresses e-mail et adresses de livraison sont masquées.
        </p>
      )}
      <div className="adm-toolbar">
        <label className="sr-only" htmlFor="recherche-commandes">
          Rechercher une commande
        </label>
        <input
          id="recherche-commandes"
          className="adm-search"
          type="search"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
          placeholder="Numéro ou e-mail"
        />
        <label className="sr-only" htmlFor="filtre-statut">
          Filtrer par statut
        </label>
        <select
          id="filtre-statut"
          className="adm-select"
          value={statut}
          onChange={(e) => {
            setStatut(e.target.value);
            setPage(0);
          }}
        >
          <option value="">Tous les statuts</option>
          {Object.entries(STATUS_LABELS).map(([valeur, libelle]) => (
            <option key={valeur} value={valeur}>
              {libelle}
            </option>
          ))}
        </select>
        <span className="adm-count" aria-live="polite">
          {total.toLocaleString("fr-FR")} commande{total > 1 ? "s" : ""}
        </span>
        <div className="adm-toolbar-end">
          <Pager page={page} pages={pages} onPage={setPage} libelle="Pages de commandes" />
          <button
            className="adm-btn"
            onClick={async () => {
              try {
                await download("/admin/orders.csv", "hanabi-commandes.csv");
                flash("Export CSV téléchargé");
              } catch (e) {
                flash(e.message, "err");
              }
            }}
          >
            <Download size={16} aria-hidden="true" /> Exporter en CSV
          </button>
        </div>
      </div>
      <div className="wh-cadre">
        <table className="adm-table">
          <thead>
            <tr>
              <th scope="col">Numéro</th>
              <th scope="col">Client</th>
              <th scope="col">Livraison</th>
              <th scope="col" className="num">
                Articles
              </th>
              <th scope="col" className="num">
                Total
              </th>
              <th scope="col">Date</th>
              <th scope="col">Statut</th>
              <th scope="col">Passer à</th>
            </tr>
          </thead>
          <tbody>
            {lignes.length === 0 && donnees && (
              <tr>
                <td colSpan={8} className="adm-vide">
                  Aucune commande ne correspond.
                </td>
              </tr>
            )}
            {lignes.map((o) => {
              const detail = ouverte === o.number;
              return (
                <Fragment key={o.number}>
                  <tr>
                    <td>
                      <button
                        className="adm-disclosure code"
                        aria-expanded={detail}
                        aria-controls={`detail-${o.number}`}
                        onClick={() => setOuverte(detail ? null : o.number)}
                      >
                        {o.number}
                        <ChevronDown size={14} aria-hidden="true" />
                      </button>
                    </td>
                    <td>{o.email}</td>
                    <td>{o.ship_city ? `${o.ship_city}` : <span className="muted">-</span>}</td>
                    <td className="num">{o.items?.reduce((s, i) => s + i.qty, 0) || "-"}</td>
                    <td className="num">{eur(o.total_cents)}</td>
                    <td>{fmtDate(o.created_at)}</td>
                    <td>
                      <StatusBadge status={o.status} />
                    </td>
                    <td className="adm-actions">
                      {o.next.length === 0 && <span className="muted">Définitif</span>}
                      {o.next.map((suivant) => (
                        <button
                          key={suivant}
                          className="adm-btn sm"
                          disabled={readonly}
                          title={readonly ? LECTURE_SEULE : undefined}
                          onClick={() => changerStatut(o.number, suivant)}
                        >
                          {STATUS_LABELS[suivant]}
                        </button>
                      ))}
                    </td>
                  </tr>
                  {detail && (
                    <tr className="adm-detail" id={`detail-${o.number}`}>
                      <td colSpan={8}>
                        <div className="adm-detail-grid">
                          <div>
                            <h3>Livraison</h3>
                            {o.ship_name ? (
                              <address>
                                {o.ship_name}
                                <br />
                                {o.ship_addr}
                                <br />
                                {o.ship_cp} {o.ship_city}
                              </address>
                            ) : (
                              <p className="muted">
                                Commande antérieure à l&apos;enregistrement des adresses.
                              </p>
                            )}
                          </div>
                          <div>
                            <h3>Articles</h3>
                            <ul>
                              {o.items.map((i) => (
                                <li key={i.name}>
                                  {i.name} <span className="muted">× {i.qty}</span>
                                  <span className="num"> {eur(i.unit_price_cents * i.qty)}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
