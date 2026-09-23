/** Droits sur ses données : récupérer, effacer. */
import { useState } from "react";
import { AlertTriangle, Download, Trash2 } from "lucide-react";

import { useT } from "../../i18n/context.jsx";
import { Compte } from "../../lib/api.js";
import { PwField } from "../ui/PasswordField.jsx";

/** Formule attendue par le serveur, répétée ici pour être affichée. */
const FORMULE = "SUPPRIMER MON COMPTE";

export function MesDonnees({ user, onEfface, flash }) {
  const t = useT();
  const [ouvert, setOuvert] = useState(false);

  return (
    <div className="stack">
      <Export flash={flash} nom={user.name} />

      <hr className="rule" />

      <div className="setting">
        <div>
          <p className="setting-title">
            <Trash2 size={16} aria-hidden="true" /> {t("rgpdDeleteTitle")}
          </p>
          <p className="muted">{t("rgpdDeleteHint")}</p>
        </div>
        <button
          className="btn btn-quiet btn-danger"
          onClick={() => setOuvert((o) => !o)}
          aria-expanded={ouvert}
        >
          {t("rgpdDeleteOpen")}
        </button>
      </div>

      {ouvert && <Suppression onEfface={onEfface} onAnnuler={() => setOuvert(false)} />}
    </div>
  );
}

function Export({ flash, nom }) {
  const t = useT();
  const [password, setPassword] = useState("");
  const [ouvert, setOuvert] = useState(false);
  const [erreur, setErreur] = useState("");
  const [envoi, setEnvoi] = useState(false);

  const telecharger = async (e) => {
    e?.preventDefault();
    if (!password) return;
    setErreur("");
    setEnvoi(true);
    try {
      const donnees = await Compte.exporterMesDonnees(password);

      // Fichier construit dans le navigateur : aucune copie ne reste sur le
      // serveur, donc rien à protéger ni à purger ensuite.
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(donnees, null, 2)], { type: "application/json" }),
      );
      const lien = document.createElement("a");
      lien.href = url;
      lien.download = `hanabi-mes-donnees-${new Date().toISOString().slice(0, 10)}.json`;
      lien.click();
      URL.revokeObjectURL(url);

      setPassword("");
      setOuvert(false);
      flash?.(t("rgpdExportDone"));
    } catch (err) {
      setErreur(err.message);
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <>
      <div className="setting">
        <div>
          <p className="setting-title">
            <Download size={16} aria-hidden="true" /> {t("rgpdExportTitle")}
          </p>
          <p className="muted">{t("rgpdExportHint")}</p>
        </div>
        <button
          className="btn btn-quiet"
          onClick={() => setOuvert((o) => !o)}
          aria-expanded={ouvert}
        >
          {t("rgpdExportOpen")}
        </button>
      </div>

      {ouvert && (
        <form className="form-stack" onSubmit={telecharger}>
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
            <button className="btn btn-primary" type="submit" disabled={!password || envoi}>
              <Download size={16} aria-hidden="true" />{" "}
              {envoi ? t("processing") : t("rgpdExportDo")}
            </button>
            <button className="btn btn-quiet" type="button" onClick={() => setOuvert(false)}>
              {t("cancel")}
            </button>
          </div>
          <p className="muted">{t("rgpdExportFormat", { nom })}</p>
        </form>
      )}
    </>
  );
}

function Suppression({ onEfface, onAnnuler }) {
  const t = useT();
  const [password, setPassword] = useState("");
  const [formule, setFormule] = useState("");
  const [erreur, setErreur] = useState("");
  const [envoi, setEnvoi] = useState(false);

  const formuleOk = formule.trim().toUpperCase() === FORMULE;
  const pret = password !== "" && formuleOk && !envoi;

  const supprimer = async (e) => {
    e.preventDefault();
    if (!pret) return;
    setErreur("");
    setEnvoi(true);
    try {
      onEfface(await Compte.supprimerMonCompte(password, formule.trim()));
    } catch (err) {
      setErreur(err.message);
      setEnvoi(false);
    }
  };

  return (
    <form className="form-stack danger-zone" onSubmit={supprimer}>
      <p className="setting-title">
        <AlertTriangle size={16} aria-hidden="true" /> {t("rgpdDeleteWarn")}
      </p>
      <ul className="bullets">
        <li>{t("rgpdDeleteGone")}</li>
        <li>{t("rgpdDeleteKept")}</li>
        <li>{t("rgpdDeleteReviews")}</li>
      </ul>

      <PwField
        label={t("secCurrentPw")}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        autoComplete="current-password"
      />

      <label className="field">
        <span>{t("rgpdDeleteType", { formule: FORMULE })}</span>
        <input
          value={formule}
          onChange={(e) => setFormule(e.target.value)}
          placeholder={FORMULE}
          autoComplete="off"
          spellCheck="false"
          aria-invalid={formule !== "" && !formuleOk ? true : undefined}
        />
      </label>

      {erreur && (
        <p className="field-error" role="alert">
          {erreur}
        </p>
      )}

      {/* Le geste sûr vient en premier et reste le plus visible */}
      <div className="actions">
        <button className="btn btn-primary" type="button" onClick={onAnnuler}>
          {t("cancel")}
        </button>
        <button className="btn btn-quiet btn-danger" type="submit" disabled={!pret}>
          <Trash2 size={16} aria-hidden="true" /> {envoi ? t("processing") : t("rgpdDeleteDo")}
        </button>
      </div>
    </form>
  );
}

export default MesDonnees;
