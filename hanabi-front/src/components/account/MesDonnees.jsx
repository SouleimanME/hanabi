/** Droits sur ses données : récupérer, effacer.
 *
 * DEUX ACTIONS QUI NE SE RESSEMBLENT PAS, et l'écran doit le montrer. Exporter
 * est anodin et réversible ; effacer ne l'est pas. Les présenter côte à côte
 * dans le même ton inviterait à cliquer sur la seconde comme sur la première.
 *
 * L'effacement est donc replié par défaut, séparé par un filet, et demande deux
 * confirmations. Ce n'est pas de la cérémonie : le mot de passe prouve qu'on est
 * bien là maintenant — une session prouve qu'on y était il y a douze heures —
 * et la formule recopiée prouve qu'on a lu ce qui va se passer.
 */
import { useState } from "react";
import { AlertTriangle, Download, Trash2 } from "lucide-react";

import { useT } from "../../i18n/context.jsx";
import { Compte } from "../../lib/api.js";
import { PwField } from "../ui/PasswordField.jsx";

/** Formule attendue par le serveur. Répétée ici pour être affichée. */
const FORMULE = "SUPPRIMER MON COMPTE";

export function MesDonnees({ user, onEfface, flash }) {
  const t = useT();
  const [ouvert, setOuvert] = useState(false);

  return (
    <div className="cpt-bloc">
      <Export flash={flash} nom={user.name} />

      <hr className="cpt-separateur" />

      <div className="cpt-ligne">
        <div>
          <span className="cpt-ligne-titre danger">
            <Trash2 size={15} /> {t("rgpdDeleteTitle")}
          </span>
          <span className="muted small">{t("rgpdDeleteHint")}</span>
        </div>
        <button className="btn-ghost danger" onClick={() => setOuvert((o) => !o)}>
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

  const telecharger = async () => {
    setErreur("");
    setEnvoi(true);
    try {
      const donnees = await Compte.exporterMesDonnees(password);

      // Fichier construit DANS le navigateur, à partir de la réponse : rien
      // n'est stocké côté serveur, donc rien n'y traîne ensuite. Un export
      // déposé sur disque et servi par URL serait une copie de plus de données
      // personnelles, à protéger et à purger.
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(donnees, null, 2)], { type: "application/json" }),
      );
      const lien = document.createElement("a");
      lien.href = url;
      const date = new Date().toISOString().slice(0, 10);
      lien.download = `hanabi-mes-donnees-${date}.json`;
      lien.click();
      URL.revokeObjectURL(url);

      setPassword("");
      setOuvert(false);
      flash?.(t("rgpdExportDone"));
    } catch (e) {
      setErreur(e.message);
    } finally {
      setEnvoi(false);
    }
  };

  return (
    <>
      <div className="cpt-ligne">
        <div>
          <span className="cpt-ligne-titre">
            <Download size={15} /> {t("rgpdExportTitle")}
          </span>
          <span className="muted small">{t("rgpdExportHint")}</span>
        </div>
        <button className="btn-ghost" onClick={() => setOuvert((o) => !o)}>
          {t("rgpdExportOpen")}
        </button>
      </div>

      {ouvert && (
        <div className="cpt-form">
          <PwField
            label={t("secCurrentPw")}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && password && telecharger()}
            autoComplete="current-password"
          />
          {erreur && (
            <p className="cpt-erreur" role="alert">
              {erreur}
            </p>
          )}
          <div className="cpt-actions">
            <button className="btn-primary" onClick={telecharger} disabled={!password || envoi}>
              <Download size={15} /> {envoi ? "…" : t("rgpdExportDo")}
            </button>
            <button className="btn-ghost" onClick={() => setOuvert(false)}>
              {t("cancel")}
            </button>
          </div>
          <p className="muted small cpt-note">{t("rgpdExportFormat", { nom })}</p>
        </div>
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

  const supprimer = async () => {
    setErreur("");
    setEnvoi(true);
    try {
      const resultat = await Compte.supprimerMonCompte(password, formule.trim());
      onEfface(resultat);
    } catch (e) {
      setErreur(e.message);
      setEnvoi(false);
    }
  };

  return (
    <div className="cpt-form cpt-danger">
      {/* CE QUI VA SE PASSER, avant de demander quoi que ce soit. Une action
          irréversible dont on découvre les effets après coup est une action
          qu'on n'a pas vraiment consentie. */}
      <p className="cpt-avertissement">
        <AlertTriangle size={15} /> {t("rgpdDeleteWarn")}
      </p>
      <ul className="cpt-liste">
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
          onKeyDown={(e) => e.key === "Enter" && pret && supprimer()}
          placeholder={FORMULE}
          autoComplete="off"
          spellCheck="false"
          aria-invalid={formule !== "" && !formuleOk ? true : undefined}
        />
      </label>

      {erreur && (
        <p className="cpt-erreur" role="alert">
          {erreur}
        </p>
      )}

      <div className="cpt-actions">
        {/* Le bouton d'annulation vient EN PREMIER et reste le plus visible :
            sur une action irréversible, c'est le geste sûr qui doit tomber sous
            la main. */}
        <button className="btn-primary" onClick={onAnnuler}>
          {t("cancel")}
        </button>
        <button className="btn-ghost danger" onClick={supprimer} disabled={!pret}>
          <Trash2 size={15} /> {envoi ? "…" : t("rgpdDeleteDo")}
        </button>
      </div>
    </div>
  );
}

export default MesDonnees;
