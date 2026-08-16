/** Confirmation d'adresse, atteinte depuis le lien recu par courriel.
 *
 * La confirmation part AU MONTAGE, sans bouton. La personne a deja cliqué dans
 * son courriel : lui demander de cliquer une seconde fois sur « confirmer »
 * ajoute une etape qui ne decide de rien. Le geste a eu lieu, il ne reste qu'a
 * l'executer et a dire ce qui s'est passe.
 *
 * L'echec n'est pas une impasse. Un lien expire ou deja utilise est le cas
 * ORDINAIRE ici - sept jours passent vite, et beaucoup de clients de messagerie
 * previsualisent les liens, ce qui les consomme. L'ecran propose donc toujours
 * une suite : se connecter pour en redemander un, ou simplement continuer,
 * puisque le compte fonctionne sans.
 */
import { useEffect, useRef, useState } from "react";
import { Check, AlertCircle, ArrowRight, Loader } from "lucide-react";

import { useT } from "../i18n/context.jsx";
import { Auth } from "../lib/api.js";

export function ConfirmerAdresse({ jeton, onContinue, onSeConnecter, onConfirme, loggedIn }) {
  const t = useT();
  const [etat, setEtat] = useState("en_cours"); // en_cours | ok | echec
  const [erreur, setErreur] = useState("");

  // Le mode strict de React monte deux fois en developpement. Sans ce garde,
  // le jeton - a USAGE UNIQUE - serait consomme par le premier appel et le
  // second afficherait « lien invalide » sur une confirmation qui a reussi.
  // AUCUNE ANNULATION AU DEMONTAGE, et c'est deliberé.
  //
  // La version precedente combinait ce garde et un drapeau `annule` pose par le
  // nettoyage de l'effet. Les deux se neutralisaient exactement : en mode
  // strict, le premier montage lance la requete, le nettoyage leve `annule`, le
  // second montage ressort aussitot sur le garde - et quand la reponse arrive,
  // elle est jetee par un drapeau que plus personne ne remettra a zero. L'ecran
  // restait sur « Confirmation en cours » alors que l'API avait repondu 200.
  //
  // Le garde suffit a lui seul : il garantit un appel unique, ce qui est la
  // seule chose qui compte pour un jeton a usage unique. Ecrire dans l'etat d'un
  // composant demonte n'a aucun effet en React 18.
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
    <main className="jeton-page">
      <div className="jeton-carte">
        {etat === "en_cours" && (
          <>
            <div className="jeton-pastille attente">
              <Loader size={26} strokeWidth={2.5} />
            </div>
            <h1>{t("verifyChecking")}</h1>
          </>
        )}

        {etat === "ok" && (
          <>
            <div className="jeton-pastille ok">
              <Check size={28} strokeWidth={3} />
            </div>
            <h1>{t("verifyOkTitle")}</h1>
            <p>{t("verifyOkBody")}</p>
            <div className="jeton-actions">
              <button className="btn-primary" onClick={onContinue}>
                {t("continueShop")} <ArrowRight size={16} />
              </button>
            </div>
          </>
        )}

        {etat === "echec" && (
          <>
            <div className="jeton-pastille echec">
              <AlertCircle size={28} strokeWidth={2.5} />
            </div>
            <h1>{t("verifyFailTitle")}</h1>
            {/* Le message du serveur, pas une reformulation : il distingue
                l'expiration de l'invalidite, ce qui n'appelle pas la meme
                reaction. */}
            <p>{erreur || t("verifyFailBody")}</p>
            <p className="jeton-rassure">{t("verifyFailHint")}</p>
            <div className="jeton-actions">
              {!loggedIn && (
                <button className="btn-primary" onClick={onSeConnecter}>
                  {t("login")}
                </button>
              )}
              <button className="btn-ghost" onClick={onContinue}>
                {t("continueShop")}
              </button>
            </div>
          </>
        )}
      </div>
    </main>
  );
}

export default ConfirmerAdresse;
