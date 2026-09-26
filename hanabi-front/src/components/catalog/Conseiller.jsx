/** Le conseiller lui-même : la demande, la réponse, les objets proposés.
 *  Chargé à la demande, seulement si le serveur a un fournisseur. */
import { useEffect, useRef, useState } from "react";
import { Check, Plus } from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import { Conseil } from "../../lib/api.js";
import { useAntiBot } from "../../hooks/useAntiBot.js";
import { ProductArt } from "../brand/ProductArt.jsx";

const EXEMPLES = [{ key: "giftEx1" }, { key: "giftEx2" }, { key: "giftEx3" }];
const DUREE_CONFIRMATION = 1600;

export default function Conseiller({ lang, onOpen, onAdd, eur }) {
  const t = useT();
  const bot = useAntiBot("conseil");
  const champ = useRef(null);
  const [demande, setDemande] = useState("");
  const [enCours, setEnCours] = useState(false);
  const [erreurChamp, setErreurChamp] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [resultat, setResultat] = useState(null);

  const envoyer = async (e) => {
    e.preventDefault();
    setErreur(null);
    if (demande.trim().length < 3) {
      setErreurChamp(t("giftTooShort"));
      champ.current?.focus();
      return;
    }
    setErreurChamp(null);
    setEnCours(true);
    try {
      const preuve = await bot.getProof();
      setResultat(await Conseil.demander(demande.trim(), lang, preuve));
    } catch (err) {
      setResultat(null);
      setErreur(
        err.status === 429 ? t("giftLimit") : err.status === 400 ? t("errAntibot") : t("giftError"),
      );
    } finally {
      setEnCours(false);
    }
  };

  const exemple = (cle) => {
    setDemande(t(cle));
    setErreurChamp(null);
    champ.current?.focus();
  };

  return (
    <section className="wrap conseil" aria-labelledby="conseil-titre">
      <div className="conseil-demande">
        <h2 id="conseil-titre">{t("giftTitle")}</h2>
        <p className="conseil-intro">{t("giftIntro")}</p>
        <form onSubmit={envoyer} noValidate>
          <input {...bot.honeypotProps} />
          <div className="field">
            <label htmlFor="conseil-champ">{t("giftLabel")}</label>
            <textarea
              id="conseil-champ"
              ref={champ}
              rows={3}
              maxLength={400}
              value={demande}
              onChange={(e) => setDemande(e.target.value)}
              placeholder={t("giftEx1")}
              aria-invalid={erreurChamp ? true : undefined}
              aria-describedby={
                erreurChamp ? "conseil-erreur conseil-confidentialite" : "conseil-confidentialite"
              }
            />
            {erreurChamp && (
              <p className="field-error" id="conseil-erreur">
                {erreurChamp}
              </p>
            )}
            <p className="conseil-note" id="conseil-confidentialite">
              {t("giftPrivacy")}
            </p>
          </div>
          <div className="conseil-actions">
            <button type="submit" className="btn btn-primary" disabled={enCours}>
              {enCours ? t("giftLoading") : t("giftSubmit")}
            </button>
          </div>
        </form>
        <div className="conseil-exemples" role="group" aria-label={t("giftExamples")}>
          <span className="conseil-exemples-titre">{t("giftExamples")}</span>
          <div className="chips">
            {EXEMPLES.map(({ key }) => (
              <button key={key} type="button" className="chip" onClick={() => exemple(key)}>
                {t(key)}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="conseil-reponse" aria-live="polite" aria-busy={enCours}>
        {erreur && (
          <div className="notice notice-error" role="alert">
            {erreur}
          </div>
        )}
        {resultat && !erreur && (
          <Reponse resultat={resultat} onOpen={onOpen} onAdd={onAdd} eur={eur} />
        )}
      </div>
    </section>
  );
}

function Reponse({ resultat, onOpen, onAdd, eur }) {
  const t = useT();
  if (resultat.vide === "budget") return <p className="conseil-message">{t("giftBudget")}</p>;
  const message = resultat.message || (resultat.choix.length ? "" : t("giftNone"));
  return (
    <>
      {message && <p className="conseil-message">{message}</p>}
      {resultat.choix.length > 0 && (
        <ol className="conseil-choix" aria-label={t("giftResults")}>
          {resultat.choix.map(({ produit, raison }) => (
            <Choix
              key={produit.id}
              p={produit}
              raison={raison}
              onOpen={onOpen}
              onAdd={onAdd}
              eur={eur}
            />
          ))}
        </ol>
      )}
    </>
  );
}

function Choix({ p, raison, onOpen, onAdd, eur }) {
  const t = useT();
  const [ajoute, setAjoute] = useState(false);
  const minuteur = useRef(null);

  useEffect(() => () => clearTimeout(minuteur.current), []);

  const ajouter = () => {
    onAdd(p.id);
    setAjoute(true);
    clearTimeout(minuteur.current);
    minuteur.current = setTimeout(() => setAjoute(false), DUREE_CONFIRMATION);
  };

  return (
    <li className="conseil-objet">
      <span className="conseil-art">
        <ProductArt art={p.art} />
      </span>
      <div className="conseil-texte">
        <h3>
          <button className="conseil-nom" onClick={() => onOpen(p)}>
            {p.name}
          </button>
        </h3>
        <p>{raison}</p>
      </div>
      <div className="conseil-pied">
        <span className="price">{eur(p.price_cents)}</span>
        <button
          className="btn btn-quiet btn-sm"
          onClick={ajouter}
          disabled={p.stock === 0}
          aria-label={t("addNamed", { name: p.name })}
        >
          <span className="swap" data-state={ajoute ? "done" : "idle"}>
            <span className="swap-idle">
              <Plus size={15} strokeWidth={2.2} aria-hidden="true" /> {t("add")}
            </span>
            <span className="swap-done" aria-hidden="true">
              <Check size={15} strokeWidth={2.2} /> {t("added")}
            </span>
          </span>
        </button>
      </div>
    </li>
  );
}
