/** Modification des informations personnelles.
 *
 * N'ENVOIE QUE CE QUI A CHANGE. Le formulaire compare chaque champ a sa valeur
 * d'origine et ne transmet que les differences. Ce n'est pas une optimisation :
 * le serveur distingue « champ absent » de « champ vide », et reposter l'objet
 * entier ecraserait avec des valeurs perimees ce qu'un autre onglet vient de
 * modifier. Envoyer moins, c'est ecraser moins.
 *
 * L'ADRESSE E-MAIL N'EST PAS ICI. Elle engage l'acces au compte, pas son
 * contenu, et se change dans la section Sécurité - mot de passe a l'appui.
 */
import { useState } from "react";
import { Check, X } from "lucide-react";

import { useT } from "../../i18n/context.jsx";
import { Compte } from "../../lib/api.js";
import { DatePicker } from "../ui/DatePicker.jsx";

const CHAMPS = ["name", "civility", "birthdate", "phone", "addr", "addr_extra", "cp", "city"];

export function InfosForm({ user, onEnregistre, onAnnuler }) {
  const t = useT();
  const [valeurs, setValeurs] = useState(() =>
    Object.fromEntries(CHAMPS.map((c) => [c, user[c] ?? ""])),
  );
  const [erreur, setErreur] = useState("");
  const [envoi, setEnvoi] = useState(false);

  const poser = (champ) => (e) =>
    setValeurs((v) => ({ ...v, [champ]: e?.target ? e.target.value : e }));

  const changes = Object.fromEntries(
    CHAMPS.filter((c) => valeurs[c] !== (user[c] ?? "")).map((c) => [c, valeurs[c]]),
  );
  const rienAEnvoyer = Object.keys(changes).length === 0;

  const enregistrer = async () => {
    if (rienAEnvoyer) return onAnnuler();
    setErreur("");
    setEnvoi(true);
    try {
      onEnregistre(await Compte.majProfil(changes));
    } catch (e) {
      setErreur(e.message);
      setEnvoi(false);
    }
  };

  const CIVILITES = [
    { value: "M", label: t("civM") },
    { value: "F", label: t("civF") },
    { value: "N", label: t("civN") },
  ];

  return (
    <div className="cpt-form">
      <div className="civ-row">
        {CIVILITES.map((c) => (
          <button
            key={c.value}
            type="button"
            className={"civ-btn" + (valeurs.civility === c.value ? " on" : "")}
            onClick={() =>
              // Un second clic retire la civilite : elle est facultative, et
              // sans cela on ne pourrait plus revenir en arriere une fois
              // choisie.
              setValeurs((v) => ({ ...v, civility: v.civility === c.value ? "" : c.value }))
            }
          >
            {c.label}
          </button>
        ))}
      </div>

      <label className="field">
        <span>{t("fullName")}</span>
        <input value={valeurs.name} onChange={poser("name")} autoComplete="name" />
      </label>

      <DatePicker value={valeurs.birthdate} onChange={(v) => poser("birthdate")(v)} />

      {/* Champ simple, et non `PhoneField`.
       *
       * `PhoneField` est NON CONTROLE : il detient son propre etat, n'accepte
       * pas de valeur initiale, et emet « +33 » des le montage. Deux
       * consequences, toutes deux fautives ici : le numero deja enregistre ne
       * s'affichait pas - donc enregistrer l'ecrasait en silence - et le
       * formulaire croyait le telephone modifie alors que personne n'y avait
       * touche, ce qui envoyait « +33 » comme numero.
       *
       * Il est fait pour la SAISIE, a l'inscription, pas pour la RELECTURE. Un
       * formulaire d'edition doit d'abord montrer ce qui existe. */}
      <label className="field">
        <span>{t("phone")}</span>
        <input
          value={valeurs.phone}
          onChange={poser("phone")}
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          placeholder="+33 6 12 34 56 78"
        />
      </label>

      <label className="field">
        <span>{t("adresse")}</span>
        <input value={valeurs.addr} onChange={poser("addr")} autoComplete="address-line1" />
      </label>
      <label className="field">
        <span>{t("adresseExtra")}</span>
        <input
          value={valeurs.addr_extra}
          onChange={poser("addr_extra")}
          autoComplete="address-line2"
        />
      </label>
      <div className="cpt-duo">
        <label className="field">
          <span>{t("cp")}</span>
          <input value={valeurs.cp} onChange={poser("cp")} autoComplete="postal-code" />
        </label>
        <label className="field">
          <span>{t("ville")}</span>
          <input value={valeurs.city} onChange={poser("city")} autoComplete="address-level2" />
        </label>
      </div>

      {erreur && (
        <p className="cpt-erreur" role="alert">
          {erreur}
        </p>
      )}

      <div className="cpt-actions">
        <button className="btn-primary" onClick={enregistrer} disabled={envoi}>
          <Check size={15} /> {envoi ? "…" : t("save")}
        </button>
        <button className="btn-ghost" onClick={onAnnuler}>
          <X size={15} /> {t("cancel")}
        </button>
        {/* Dire ce qui va partir, plutot que de laisser deviner. Le compte
            change aussi la reponse a « pourquoi Enregistrer ne fait rien ». */}
        <span className="cpt-compte muted small">
          {rienAEnvoyer ? t("noChange") : t("nChanges", { n: Object.keys(changes).length })}
        </span>
      </div>
    </div>
  );
}

export default InfosForm;
