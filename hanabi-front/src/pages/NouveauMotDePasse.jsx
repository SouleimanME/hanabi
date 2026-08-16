/** Choix d'un nouveau mot de passe, depuis le lien recu par courriel.
 *
 * Contrairement a l'ecran de confirmation d'adresse, rien ne part au montage :
 * il y a ici une decision a prendre, et une saisie a faire. Le jeton n'est
 * consomme qu'a l'envoi.
 *
 * MEMES REGLES QU'A L'INSCRIPTION, et affichees en direct. Un parcours de
 * recuperation n'est pas une occasion d'accepter un mot de passe plus faible,
 * et decouvrir un refus apres avoir tout saisi - depuis un lien a usage unique,
 * qui plus est - est la pire des issues. Le serveur reste seul juge : il refuse
 * en plus les mots de passe compromis et ceux qui reprennent le nom ou
 * l'adresse, ce qui ne se verifie pas ici.
 */
import { useState } from "react";
import { AlertCircle, ArrowRight, KeyRound } from "lucide-react";

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
  const pretAEnvoyer = isPasswordStrong(pw) && identiques && !envoi;

  const envoyer = async () => {
    if (!pretAEnvoyer) {
      // Le message dit CE QUI manque, plutot que « formulaire invalide » : les
      // deux causes possibles n'appellent pas la meme correction.
      setErreur(identiques ? t("pwTooWeak") : t("pwMismatch"));
      return;
    }
    setErreur("");
    setEnvoi(true);
    try {
      const { user } = await Auth.resetPassword(jeton, pw);
      // Le serveur renvoie un jeton d'acces : on est connecte dans la foulee.
      // Repasser par l'ecran de connexion apres avoir prouve son identite et
      // choisi un mot de passe serait une etape de trop.
      onReussite(user);
    } catch (e) {
      setErreur(e.message);
      setEnvoi(false);
    }
  };

  return (
    <main className="jeton-page">
      <div className="jeton-carte large">
        <div className="jeton-pastille neutre">
          <KeyRound size={26} strokeWidth={2.5} />
        </div>
        <h1>{t("resetTitle")}</h1>
        <p>{t("resetBody")}</p>

        <div className="jeton-form">
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
            onKeyDown={(e) => e.key === "Enter" && envoyer()}
            autoComplete="new-password"
            name="confirm-password"
            invalid={confirmation !== "" && !identiques}
          />

          {erreur && (
            <p className="jeton-erreur" role="alert">
              <AlertCircle size={15} /> {erreur}
            </p>
          )}

          <div className="jeton-actions">
            <button className="btn-primary" onClick={envoyer} disabled={!pretAEnvoyer}>
              {envoi ? t("resetSending") : t("resetSubmit")} <ArrowRight size={16} />
            </button>
            <button className="btn-ghost" onClick={onContinue}>
              {t("cancel")}
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}

export default NouveauMotDePasse;
