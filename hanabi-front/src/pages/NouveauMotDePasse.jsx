/** Nouveau mot de passe, depuis le lien recu par courriel. */
import { useState } from "react";
import { ArrowRight, KeyRound } from "lucide-react";

import { useT } from "../i18n/context.jsx";
import { PwField, PwStrength, PwChecklist } from "../components/ui/PasswordField.jsx";
import { isPasswordStrong } from "../lib/password.js";
import { Auth } from "../lib/api.js";

export function NouveauMotDePasse({ jeton, onReussite, onContinue }) {
  const t = useT();
  const [pw, setPw] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [erreur, setErreur] = useState("");
  const [envoi, setEnvoi] = useState(false);

  const identiques = pw !== "" && pw === confirmation;
  const pret = isPasswordStrong(pw) && identiques && !envoi;

  const envoyer = async (e) => {
    e.preventDefault();
    if (!pret) {
      setErreur(identiques ? t("pwTooWeak") : t("pwMismatch"));
      return;
    }
    setErreur("");
    setEnvoi(true);
    try {
      // Le serveur rend une session : on est connecte dans la foulee
      const { user } = await Auth.resetPassword(jeton, pw);
      onReussite(user);
    } catch (err) {
      setErreur(err.message);
      setEnvoi(false);
    }
  };

  return (
    <main id="contenu" className="wrap page">
      <section className="token-card token-card-form" aria-labelledby="reset-titre">
        <span className="token-mark" aria-hidden="true">
          <KeyRound size={26} />
        </span>
        <h1 id="reset-titre">{t("resetTitle")}</h1>
        <p>{t("resetBody")}</p>

        <form className="form-stack" onSubmit={envoyer}>
          <PwField
            label={t("resetNewLabel")}
            value={pw}
            onChange={(e) => setPw(e.target.value)}
            autoComplete="new-password"
            name="new-password"
          />
          {pw && (
            <>
              <PwStrength value={pw} />
              <PwChecklist value={pw} />
            </>
          )}
          <PwField
            label={t("pwConfirmLabel")}
            value={confirmation}
            onChange={(e) => setConfirmation(e.target.value)}
            autoComplete="new-password"
            name="confirm-password"
            invalid={confirmation !== "" && !identiques}
          />

          {erreur && (
            <p className="field-error" role="alert">
              {erreur}
            </p>
          )}

          <div className="actions">
            <button className="btn btn-primary" type="submit" disabled={!pret}>
              {envoi ? t("resetSending") : t("resetSubmit")}{" "}
              <ArrowRight size={18} aria-hidden="true" />
            </button>
            <button className="btn btn-quiet" type="button" onClick={onContinue}>
              {t("cancel")}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}

export default NouveauMotDePasse;
