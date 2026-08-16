/** Sécurité du compte : mot de passe et adresse de connexion.
 *
 * CES DEUX-LÀ SONT ENSEMBLE, et pas avec les informations personnelles, parce
 * qu'ils ne relèvent pas de la même chose : le nom et l'adresse postale sont le
 * CONTENU du compte, le mot de passe et l'e-mail en sont l'ACCÈS. Les deux
 * exigent donc le mot de passe courant — une session prouve qu'on était là il y
 * a douze heures, pas qu'on est là maintenant, et un poste laissé ouvert
 * quelques minutes suffirait sinon à verrouiller le propriétaire dehors.
 */
import { useState } from "react";
import { KeyRound, Mail } from "lucide-react";

import { useT } from "../../i18n/context.jsx";
import { Compte } from "../../lib/api.js";
import { PwField, PwStrength, PwChecklist } from "../ui/PasswordField.jsx";
import { isPasswordStrong } from "../../lib/password.js";

export function Securite({ user, onProfil, flash }) {
  const t = useT();
  const [section, setSection] = useState(null); // null | "mdp" | "email"

  return (
    <div className="cpt-bloc">
      <div className="cpt-ligne">
        <div>
          <span className="cpt-ligne-titre">
            <KeyRound size={15} /> {t("password")}
          </span>
          <span className="muted small">{t("secPwHint")}</span>
        </div>
        <button className="btn-ghost" onClick={() => setSection(section === "mdp" ? null : "mdp")}>
          {t("change")}
        </button>
      </div>
      {section === "mdp" && (
        <FormMotDePasse
          onFini={() => {
            setSection(null);
            flash?.(t("secPwDone"));
          }}
          onAnnuler={() => setSection(null)}
        />
      )}

      <div className="cpt-ligne">
        <div>
          <span className="cpt-ligne-titre">
            <Mail size={15} /> {t("email")}
          </span>
          <span className="muted small mono">{user.email}</span>
        </div>
        <button
          className="btn-ghost"
          onClick={() => setSection(section === "email" ? null : "email")}
        >
          {t("change")}
        </button>
      </div>
      {section === "email" && (
        <FormEmail
          onFini={(profil) => {
            setSection(null);
            onProfil(profil);
            flash?.(t("secMailDone"));
          }}
          onAnnuler={() => setSection(null)}
        />
      )}
    </div>
  );
}

function FormMotDePasse({ onFini, onAnnuler }) {
  const t = useT();
  const [ancien, setAncien] = useState("");
  const [nouveau, setNouveau] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [erreur, setErreur] = useState("");
  const [envoi, setEnvoi] = useState(false);

  const identiques = nouveau !== "" && nouveau === confirmation;
  const pret = ancien !== "" && isPasswordStrong(nouveau) && identiques && !envoi;

  const envoyer = async () => {
    if (!pret) {
      setErreur(identiques ? t("pwTooWeak") : t("pwMismatch"));
      return;
    }
    setErreur("");
    setEnvoi(true);
    try {
      await Compte.changerMotDePasse(ancien, nouveau);
      onFini();
    } catch (e) {
      setErreur(e.message);
      setEnvoi(false);
    }
  };

  return (
    <div className="cpt-form">
      <PwField
        label={t("secCurrentPw")}
        value={ancien}
        onChange={(e) => setAncien(e.target.value)}
        autoComplete="current-password"
      />
      <PwField
        label={t("secNewPw")}
        value={nouveau}
        onChange={(e) => setNouveau(e.target.value)}
        autoComplete="new-password"
      />
      {nouveau && (
        <>
          <PwStrength value={nouveau} />
          <PwChecklist value={nouveau} />
        </>
      )}
      <PwField
        label={t("pwConfirmLabel")}
        value={confirmation}
        onChange={(e) => setConfirmation(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && envoyer()}
        autoComplete="new-password"
        invalid={confirmation !== "" && !identiques}
      />
      {erreur && (
        <p className="cpt-erreur" role="alert">
          {erreur}
        </p>
      )}
      <div className="cpt-actions">
        <button className="btn-primary" onClick={envoyer} disabled={!pret}>
          {envoi ? "…" : t("save")}
        </button>
        <button className="btn-ghost" onClick={onAnnuler}>
          {t("cancel")}
        </button>
      </div>
    </div>
  );
}

function FormEmail({ onFini, onAnnuler }) {
  const t = useT();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [erreur, setErreur] = useState("");
  const [envoi, setEnvoi] = useState(false);

  const pret = email.includes("@") && password !== "" && !envoi;

  const envoyer = async () => {
    setErreur("");
    setEnvoi(true);
    try {
      onFini(await Compte.changerEmail(email.trim(), password));
    } catch (e) {
      setErreur(e.message);
      setEnvoi(false);
    }
  };

  return (
    <div className="cpt-form">
      {/* Dit AVANT la saisie ce qui va se passer : la nouvelle adresse repart
          non confirmée, et un lien y sera envoyé. Découvrir cela après coup
          ressemblerait à une régression. */}
      <p className="muted small cpt-note">{t("secMailHint")}</p>
      <label className="field">
        <span>{t("secNewMail")}</span>
        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="toi@exemple.fr"
          inputMode="email"
          autoCapitalize="none"
          spellCheck="false"
          autoComplete="email"
        />
      </label>
      <PwField
        label={t("secCurrentPw")}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && envoyer()}
        autoComplete="current-password"
      />
      {erreur && (
        <p className="cpt-erreur" role="alert">
          {erreur}
        </p>
      )}
      <div className="cpt-actions">
        <button className="btn-primary" onClick={envoyer} disabled={!pret}>
          {envoi ? "…" : t("save")}
        </button>
        <button className="btn-ghost" onClick={onAnnuler}>
          {t("cancel")}
        </button>
      </div>
    </div>
  );
}

export default Securite;
