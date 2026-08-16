/** Moyens de paiement enregistrés.
 *
 * CE QUI NE QUITTE JAMAIS CETTE PAGE : le numéro de carte et le cryptogramme.
 * Le formulaire les lit pour en déduire le réseau, les quatre derniers chiffres
 * et l'expiration - et c'est tout ce qui part sur le réseau. Le serveur n'a
 * donc rien à protéger qu'il ne détienne pas, ce qui maintient l'application
 * hors du périmètre PCI-DSS.
 *
 * Dans une boutique réelle, ces champs n'appartiendraient même pas au site :
 * on intègre l'iframe du prestataire (Stripe Elements et équivalents), qui rend
 * un jeton. Le partage des rôles est identique ici, le jeton étant simulé côté
 * serveur. Le reste du code ne changerait pas d'une ligne.
 */
import { useCallback, useEffect, useState } from "react";
import { CreditCard, Plus, Star, Trash2, ShieldCheck } from "lucide-react";

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

  if (erreur) return <p className="cpt-erreur">{erreur}</p>;
  if (!liste) return <p className="muted small">…</p>;

  return (
    <div className="cpt-bloc">
      <p className="cpt-avis">
        <ShieldCheck size={14} /> {t("payNotice")}
      </p>

      {liste.length === 0 && !ouvert && <p className="muted small">{t("payEmpty")}</p>}

      {liste.length > 0 && (
        <ul className="cartes">
          {liste.map((m) => (
            <li key={m.id} className={"carte" + (m.defaut ? " defaut" : "")}>
              <CreditCard size={18} />
              <div className="carte-info">
                <span className="carte-nom">
                  {NOMS_RESEAU[m.reseau] || t("payCard")}
                  <span className="mono carte-num"> •••• {m.quatre_derniers}</span>
                </span>
                <span className="muted small">
                  {t("payExpires", {
                    d: `${String(m.exp_mois).padStart(2, "0")}/${String(m.exp_annee).slice(-2)}`,
                  })}
                  {m.libelle ? ` · ${m.libelle}` : ""}
                </span>
              </div>
              {m.defaut ? (
                <span className="carte-defaut">
                  <Star size={12} /> {t("payDefault")}
                </span>
              ) : (
                <button
                  className="lien-oubli"
                  onClick={() => agir(() => Compte.paiementParDefaut(m.id), t("payDefaultSet"))}
                >
                  {t("payMakeDefault")}
                </button>
              )}
              <button
                className="icon-btn carte-suppr"
                aria-label={t("payDelete")}
                onClick={() => agir(() => Compte.supprimerPaiement(m.id), t("payDeleted"))}
              >
                <Trash2 size={15} />
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
        <button className="btn-ghost cpt-ajout" onClick={() => setOuvert(true)}>
          <Plus size={15} /> {t("payAdd")}
        </button>
      )}
    </div>
  );
}

/** Saisie d'une carte. Ce composant est le seul du projet à voir un numéro. */
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

  const envoyer = async () => {
    if (!pret) {
      setErreur(numeroOk ? t("payBadExpiry") : t("payBadNumber"));
      return;
    }
    setErreur("");
    setEnvoi(true);

    // LE MOMENT QUI COMPTE. Le numéro est réduit ici, dans le navigateur, à ce
    // qui sert à le reconnaître. Rien d'autre n'est construit, donc rien
    // d'autre ne peut partir.
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
    } catch (e) {
      setErreur(e.message);
      setEnvoi(false);
    }
  };

  return (
    <div className="cpt-form carte-form">
      <label className="field">
        <span>{t("cardNumber")}</span>
        <input
          value={formatCardNumber(numero)}
          onChange={(e) => setNumero(e.target.value)}
          placeholder="4242 4242 4242 4242"
          inputMode="numeric"
          autoComplete="cc-number"
        />
        {reseau.label && <span className="carte-reseau muted small">{reseau.label}</span>}
      </label>

      <div className="cpt-duo">
        <label className="field">
          <span>{t("cardExpiry")}</span>
          <input
            value={formatExpiry(expiration)}
            onChange={(e) => setExpiration(e.target.value)}
            placeholder="12/30"
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

      {/* Aucun champ de cryptogramme : il ne sert qu'à autoriser un paiement,
          jamais à enregistrer une carte, et le demander ici inviterait à le
          transmettre pour rien. */}
      <p className="muted small cpt-note">{t("payNoCvc")}</p>

      {erreur && (
        <p className="cpt-erreur" role="alert">
          {erreur}
        </p>
      )}

      <div className="cpt-actions">
        <button className="btn-primary" onClick={envoyer} disabled={!pret}>
          {envoi ? "…" : t("payAdd")}
        </button>
        <button className="btn-ghost" onClick={onAnnuler}>
          {t("cancel")}
        </button>
      </div>
    </div>
  );
}

export default Paiements;
