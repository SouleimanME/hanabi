/** Clients : recherche et pagination cote serveur, alertes de retour en stock. */
import { useCallback, useEffect, useState } from "react";

import { api } from "../api.js";
import { eur, fmtDate, LECTURE_SEULE } from "../format.js";
import { Pager, SousTitre } from "../ui.jsx";

const PAGE = 40;

export function Users({ items, setItems, alerts, flash, readonly }) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);

  const charger = useCallback(
    async (q, p) => {
      try {
        const query = new URLSearchParams({ limit: PAGE, offset: p * PAGE });
        if (q.trim()) query.set("q", q.trim());
        setItems(await api(`/admin/users?${query}`));
      } catch (e) {
        flash(e.message, "err");
      }
    },
    [setItems, flash],
  );

  // Saisie temporisee : une requete par caractere saturerait l'API
  useEffect(() => {
    const minuteur = setTimeout(() => charger(search, page), 250);
    return () => clearTimeout(minuteur);
  }, [search, page, charger]);

  const total = items?.total ?? 0;
  const lignes = items?.items ?? [];
  const pages = Math.max(1, Math.ceil(total / PAGE));

  const basculerAdmin = async (u) => {
    const promotion = !u.is_admin;
    if (
      !confirm(
        promotion
          ? `Donner les droits d'administration à ${u.name} ?`
          : `Retirer les droits de ${u.name} ?`,
      )
    )
      return;
    try {
      await api(`/admin/users/${u.id}/admin?is_admin=${promotion}`, { method: "PATCH" });
      flash("Droits mis à jour");
      charger(search, page);
    } catch (e) {
      flash(e.message, "err");
    }
  };

  return (
    <div>
      {alerts.length > 0 && (
        <section className="adm-alerts">
          <SousTitre>Alertes de retour en stock ({alerts.length})</SousTitre>
          <p className="adm-legend">
            Chaque personne reçoit un e-mail au réassort de l&apos;objet, puis sa demande se ferme.
          </p>
          <div className="wh-cadre">
            <table className="adm-table">
              <thead>
                <tr>
                  <th scope="col">Produit</th>
                  <th scope="col">E-mail</th>
                  <th scope="col">Date</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((a) => (
                  <tr key={a.id}>
                    <td>{a.product ?? `#${a.product_id}`}</td>
                    <td>{a.email}</td>
                    <td>{fmtDate(a.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {items?.masque && (
        <p className="adm-warn">
          Compte de démonstration : noms, adresses e-mail et villes sont masqués.
        </p>
      )}

      <div className="adm-toolbar">
        <label className="sr-only" htmlFor="recherche-clients">
          Rechercher un client
        </label>
        <input
          id="recherche-clients"
          className="adm-search"
          type="search"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
          placeholder="Nom, e-mail ou ville"
        />
        <span className="adm-count" aria-live="polite">
          {total.toLocaleString("fr-FR")} client{total > 1 ? "s" : ""}
        </span>
        <div className="adm-toolbar-end">
          <Pager page={page} pages={pages} onPage={setPage} libelle="Pages de clients" />
        </div>
      </div>
      <div className="wh-cadre">
        <table className="adm-table">
          <thead>
            <tr>
              <th scope="col">Nom</th>
              <th scope="col">E-mail</th>
              <th scope="col">Ville</th>
              <th scope="col" className="num">
                Commandes
              </th>
              <th scope="col" className="num">
                CA
              </th>
              <th scope="col">Rôle</th>
              <th scope="col">Inscrit</th>
              <th scope="col">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {lignes.map((u) => (
              <tr key={u.id}>
                <td>
                  <strong>
                    {u.civility ? `${u.civility}. ` : ""}
                    {u.name}
                  </strong>
                </td>
                <td>{u.email}</td>
                <td>{u.city || "-"}</td>
                <td className="num">{u.order_count}</td>
                <td className="num">{eur(u.total_spent_cents)}</td>
                <td>
                  {u.is_admin ? (
                    <span className="adm-tag admin">Admin</span>
                  ) : (
                    <span className="adm-tag">Client</span>
                  )}
                </td>
                <td>{fmtDate(u.created_at)}</td>
                <td className="adm-actions">
                  <button
                    className="adm-btn sm"
                    disabled={readonly}
                    title={readonly ? LECTURE_SEULE : undefined}
                    onClick={() => basculerAdmin(u)}
                  >
                    {u.is_admin ? "Retirer admin" : "Rendre admin"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
