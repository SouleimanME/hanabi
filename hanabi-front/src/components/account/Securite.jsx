/** Sécurité du compte : mot de passe et adresse de connexion. */
import { useState } from "react";
import { KeyRound, Mail } from "lucide-react";

import { useT } from "../../i18n/context.jsx";
import { Compte } from "../../lib/api.js";
import { PwField, PwStrength, PwChecklist } from "../ui/PasswordField.jsx";
import { isPasswordStrong } from "../../lib/password.js";

export function Securite({ user, onProfil, flash }) {
  const t = useT();
  const [section, setSection] = useState(null); // null | "mdp" | "email"
  const basculer = (nom) => setSection((s) => (s === nom ? null : nom));

  return (
    <div className="stack">
      <div className="setting">
        <div>
          <p className="setting-title">
            <KeyRound size={16} aria-hidden="true" /> {t("password")}
          </p>
          <p className="muted">{t("secPwHint")}</p>
        </div>
        <button
          className="btn btn-quiet"
          onClick={() => basculer("mdp")}
          aria-expanded={section === "mdp"}
        >
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

      <div className="setting">
        <div>
          <p className="setting-title">
            <Mail size={16} aria-hidden="true" /> {t("email")}
          </p>
          <p className="muted">{user.email}</p>
        </div>
        <button
          className="btn btn-quiet"
          onClick={() => basculer("email")}
          aria-expanded={section === "email"}
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

  const envoyer = async (e) => {
    e.preventDefault();
    if (!pret) {
      setErreur(identiques ? t("pwTooWeak") : t("pwMismatch"));
      return;
    }
    setErreur("");
    setEnvoi(true);
    try {
      await Compte.changerMotDePasse(ancien, nouveau);
      onFini();
    } catch (err) {
      setErreur(err.message);
      setEnvoi(false);
    }
  };

  return (
    <form className="form-stack" onSubmit={envoyer}>
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
        autoComplete="new-password"
        invalid={confirmation !== "" && !identiques}
      />
      {erreur && (
        <p className="field-error" role="alert">
          {erreur}
        </p>
      )}
      <div className="actions">
        <button className="btn btn-primary" type="submit" disabled={!pret}>
          {envoi ? t("processing") : t("save")}
        </button>
        <button className="btn btn-quiet" type="button" onClick={onAnnuler}>
          {t("cancel")}
        </button>
      </div>
    </form>
  );
}

function FormEmail({ onFini, onAnnuler }) {
  const t = useT();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [erreur, setErreur] = useState("");
  const [envoi, setEnvoi] = useState(false);

  const pret = email.includes("@") && password !== "" && !envoi;

  const envoyer = async (e) => {
    e.preventDefault();
    if (!pret) return;
    setErreur("");
    setEnvoi(true);
    try {
      onFini(await Compte.changerEmail(email.trim(), password));
    } catch (err) {
      setErreur(err.message);
      setEnvoi(false);
    }
  };

  return (
    <form className="form-stack" onSubmit={envoyer}>
      {/* Dit avant la saisie que la nouvelle adresse devra être confirmée */}
      <p className="muted">{t("secMailHint")}</p>
      <label className="field">
        <span>{t("secNewMail")}</span>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
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
        autoComplete="current-password"
      />
      {erreur && (
        <p className="field-error" role="alert">
          {erreur}
        </p>
      )}
      <div className="actions">
        <button className="btn btn-primary" type="submit" disabled={!pret}>
          {envoi ? t("processing") : t("save")}
        </button>
        <button className="btn btn-quiet" type="button" onClick={onAnnuler}>
          {t("cancel")}
        </button>
      </div>
    </form>
  );
}

export default Securite;
