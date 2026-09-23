/** Confirmation d'adresse, depuis le lien recu par courriel. */
import { useEffect, useRef, useState } from "react";
import { Check, AlertCircle, ArrowRight, Loader } from "lucide-react";

import { useT } from "../i18n/context.jsx";
import { Auth } from "../lib/api.js";

export function ConfirmerAdresse({ jeton, onContinue, onSeConnecter, onConfirme, loggedIn }) {
  const t = useT();
  const [etat, setEtat] = useState("en_cours"); // en_cours | ok | echec
  const [erreur, setErreur] = useState("");

  // Le mode strict monte deux fois en developpement
  const envoye = useRef(false);

  useEffect(() => {
    if (envoye.current || !jeton) return;
    envoye.current = true;

    (async () => {
      try {
        const compte = await Auth.verifyEmail(jeton);
        setEtat("ok");
        onConfirme?.(compte);
      } catch (e) {
        setErreur(e.message);
        setEtat("echec");
      }
    })();
  }, [jeton, onConfirme]);

  return (
    <main id="contenu" className="wrap page">
      <section className="token-card" aria-live="polite">
        {etat === "en_cours" && (
          <>
            <span className="token-mark" aria-hidden="true">
              <Loader size={26} />
            </span>
            <h1>{t("verifyChecking")}</h1>
          </>
        )}

        {etat === "ok" && (
          <>
            <span className="token-mark" aria-hidden="true">
              <Check size={28} strokeWidth={2.4} />
            </span>
            <h1>{t("verifyOkTitle")}</h1>
            <p>{t("verifyOkBody")}</p>
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
            <h1>{t("verifyFailTitle")}</h1>
            {/* Le message du serveur distingue l'expiration de l'invalidite */}
            <p>{erreur || t("verifyFailBody")}</p>
            <p className="muted">{t("verifyFailHint")}</p>
            <div className="actions actions-center">
              {!loggedIn && (
                <button className="btn btn-primary" onClick={onSeConnecter}>
                  {t("login")}
                </button>
              )}
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

export default ConfirmerAdresse;
