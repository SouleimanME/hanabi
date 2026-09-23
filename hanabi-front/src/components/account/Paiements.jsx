/** Moyens de paiement enregistrés. */
import { useCallback, useEffect, useState } from "react";
import { CreditCard, Plus, Trash2 } from "lucide-react";

import { useT } from "../../i18n/context.jsx";
import { Compte } from "../../lib/api.js";
import {
  detectBrand,
  digitsOnly,
  formatCardNumber,
  cardNumberValid,
  formatExpiry,
  expiryValid,
} from "../../lib/card.js";

const NOMS_RESEAU = { visa: "Visa", mastercard: "Mastercard", amex: "American Express" };

export function Paiements({ flash }) {
  const t = useT();
  const [liste, setListe] = useState(null);
  const [erreur, setErreur] = useState("");
  const [ouvert, setOuvert] = useState(false);

  const charger = useCallback(() => {
    Compte.paiements()
      .then(setListe)
      .catch((e) => setErreur(e.message));
  }, []);

  useEffect(charger, [charger]);

  const agir = async (action, message) => {
    try {
      await action();
      charger();
      if (message) flash?.(message);
    } catch (e) {
      flash?.(e.message);
    }
  };

  if (erreur) return <p className="field-error">{erreur}</p>;
  if (!liste) return <p className="muted">{t("loading")}</p>;

  return (
    <div className="stack">
      <p className="muted">{t("payNotice")}</p>

      {liste.length === 0 && !ouvert && <p>{t("payEmpty")}</p>}

      {liste.length > 0 && (
        <ul className="cards-list">
          {liste.map((m) => (
            <li key={m.id} className="saved-card">
              <CreditCard size={20} aria-hidden="true" />
              <div className="saved-card-main">
                <span>
                  {NOMS_RESEAU[m.reseau] || t("payCard")}
                  <span className="code"> •••• {m.quatre_derniers}</span>
                </span>
                <span className="muted">
                  {t("payExpires", {
                    d: `${String(m.exp_mois).padStart(2, "0")}/${String(m.exp_annee).slice(-2)}`,
                  })}
                  {m.libelle ? ` · ${m.libelle}` : ""}
                </span>
              </div>
              {m.defaut ? (
                <span className="tag">{t("payDefault")}</span>
              ) : (
                <button
                  className="link"
                  onClick={() => agir(() => Compte.paiementParDefaut(m.id), t("payDefaultSet"))}
                >
                  {t("payMakeDefault")}
                </button>
              )}
              <button
                className="icon-btn"
                aria-label={t("payDelete")}
                onClick={() => agir(() => Compte.supprimerPaiement(m.id), t("payDeleted"))}
              >
                <Trash2 size={18} />
              </button>
            </li>
          ))}
        </ul>
      )}

      {ouvert ? (
        <FormulaireCarte
          onAjoute={() => {
            setOuvert(false);
            charger();
            flash?.(t("payAdded"));
          }}
          onAnnuler={() => setOuvert(false)}
        />
      ) : (
        <div>
          <button className="btn btn-quiet" onClick={() => setOuvert(true)}>
            <Plus size={16} aria-hidden="true" /> {t("payAdd")}
          </button>
        </div>
      )}
    </div>
  );
}

/** Saisie d'une carte : le seul composant du projet qui voit un numéro. */
function FormulaireCarte({ onAjoute, onAnnuler }) {
  const t = useT();
  const [numero, setNumero] = useState("");
  const [expiration, setExpiration] = useState("");
  const [libelle, setLibelle] = useState("");
  const [erreur, setErreur] = useState("");
  const [envoi, setEnvoi] = useState(false);

  const reseau = detectBrand(numero);
  const numeroOk = cardNumberValid(numero);
  const expOk = expiryValid(expiration);
  const pret = numeroOk && expOk && !envoi;

  const envoyer = async (e) => {
    e.preventDefault();
    if (!pret) {
      setErreur(numeroOk ? t("payBadExpiry") : t("payBadNumber"));
      return;
    }
    setErreur("");
    setEnvoi(true);

    // Le numéro est réduit ici à ce qui sert à le reconnaître ; rien d'autre
    // n'est construit, donc rien d'autre ne peut partir.
    const chiffres = digitsOnly(numero);
    const exp = digitsOnly(expiration);

    try {
      await Compte.ajouterPaiement({
        reseau: reseau.id,
        quatre_derniers: chiffres.slice(-4),
        exp_mois: Number(exp.slice(0, 2)),
        exp_annee: 2000 + Number(exp.slice(2)),
        libelle: libelle.trim() || null,
      });
      onAjoute();
    } catch (err) {
      setErreur(err.message);
      setEnvoi(false);
    }
  };

  return (
    <form className="form-stack" onSubmit={envoyer} noValidate>
      <label className="field">
        <span>{t("cardNumber")}</span>
        <span className="card-input">
          <input
            value={formatCardNumber(numero)}
            onChange={(e) => setNumero(e.target.value)}
            placeholder="4242 4242 4242 4242"
            inputMode="numeric"
            autoComplete="cc-number"
          />
          {reseau.label && <span className="card-brand">{reseau.label}</span>}
        </span>
      </label>

      <div className="field-row">
        <label className="field">
          <span>{t("cardExpiry")}</span>
          <input
            value={formatExpiry(expiration)}
            onChange={(e) => setExpiration(e.target.value)}
            placeholder={t("expPh")}
            inputMode="numeric"
            autoComplete="cc-exp"
          />
        </label>
        <label className="field">
          <span>{t("cardLabel")}</span>
          <input
            value={libelle}
            onChange={(e) => setLibelle(e.target.value)}
            placeholder={t("cardLabelHint")}
            maxLength={40}
          />
        </label>
      </div>

      {/* Pas de cryptogramme : il autorise un paiement, il n'enregistre pas une carte */}
      <p className="muted">{t("payNoCvc")}</p>

      {erreur && (
        <p className="field-error" role="alert">
          {erreur}
        </p>
      )}

      <div className="actions">
        <button className="btn btn-primary" type="submit" disabled={!pret}>
          {envoi ? t("processing") : t("payAdd")}
        </button>
        <button className="btn btn-quiet" type="button" onClick={onAnnuler}>
          {t("cancel")}
        </button>
      </div>
    </form>
  );
}

export default Paiements;
