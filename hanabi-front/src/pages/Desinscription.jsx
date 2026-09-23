/** Désinscription de la lettre, depuis le lien signé de chaque courriel. Un clic suffit. */
import { useEffect, useRef, useState } from "react";
import { Check, AlertCircle, ArrowRight, Loader } from "lucide-react";

import { useT } from "../i18n/context.jsx";
import { Newsletter } from "../lib/api.js";

export function Desinscription({ lien, onContinue }) {
  const t = useT();
  const [etat, setEtat] = useState("en_cours"); // en_cours | ok | echec
  const [erreur, setErreur] = useState("");
  // Adresse masquée rendue par le serveur : dit laquelle, sans l'afficher
  const [adresse, setAdresse] = useState(null);

  // Le mode strict monte deux fois en développement
  const envoye = useRef(false);

  useEffect(() => {
    if (envoye.current || !lien) return;
    envoye.current = true;

    (async () => {
      try {
        const res = await Newsletter.unsubscribe(lien.id, lien.signature);
        setAdresse(res?.email ?? null);
        setEtat("ok");
      } catch (e) {
        setErreur(e.message);
        setEtat("echec");
      }
    })();
  }, [lien]);

  return (
    <main id="contenu" className="wrap page">
      <section className="token-card" aria-live="polite">
        {etat === "en_cours" && (
          <>
            <span className="token-mark" aria-hidden="true">
              <Loader size={26} />
            </span>
            <h1>{t("unsubChecking")}</h1>
          </>
        )}

        {etat === "ok" && (
          <>
            <span className="token-mark" aria-hidden="true">
              <Check size={28} strokeWidth={2.4} />
            </span>
            <h1>{t("unsubOkTitle")}</h1>
            {adresse && <p className="code">{adresse}</p>}
            <p>{t("unsubOkBody")}</p>
            <p className="muted">{t("unsubOkHint")}</p>
            <div className="actions actions-center">
              <button className="btn btn-primary" onClick={onContinue}>
                {t("continueShop")} <ArrowRight size={18} aria-hidden="true" />
              </button>
            </div>
          </>
        )}

        {etat === "echec" && (
          <>
            <span className="token-mark token-mark-alert" aria-hidden="true">
              <AlertCircle size={28} />
            </span>
            <h1>{t("unsubFailTitle")}</h1>
            <p>{erreur || t("unsubFailBody")}</p>
            <div className="actions actions-center">
              <button className="btn btn-quiet" onClick={onContinue}>
                {t("continueShop")}
              </button>
            </div>
          </>
        )}
      </section>
    </main>
  );
}

export default Desinscription;
