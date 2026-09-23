/** Modification des informations personnelles. */
import { useState } from "react";
import { Check } from "lucide-react";

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

  const enregistrer = async (e) => {
    e.preventDefault();
    if (rienAEnvoyer) return onAnnuler();
    setErreur("");
    setEnvoi(true);
    try {
      onEnregistre(await Compte.majProfil(changes));
    } catch (err) {
      setErreur(err.message);
      setEnvoi(false);
    }
  };

  const CIVILITES = [
    { value: "M", label: t("civM") },
    { value: "F", label: t("civF") },
    { value: "N", label: t("civN") },
  ];

  return (
    <form className="form-stack" onSubmit={enregistrer}>
      <fieldset className="field">
        <legend>{t("civility")}</legend>
        <div className="chips">
          {CIVILITES.map((c) => (
            <button
              key={c.value}
              type="button"
              className="chip"
              aria-pressed={valeurs.civility === c.value}
              // Un second clic retire la civilite : elle est facultative
              onClick={() =>
                setValeurs((v) => ({ ...v, civility: v.civility === c.value ? "" : c.value }))
              }
            >
              {c.label}
            </button>
          ))}
        </div>
      </fieldset>

      <label className="field">
        <span>{t("fullName")}</span>
        <input value={valeurs.name} onChange={poser("name")} autoComplete="name" />
      </label>

      <DatePicker value={valeurs.birthdate} onChange={(v) => poser("birthdate")(v)} />

      {/* Champ simple plutot que PhoneField : ce dernier est fait pour la
          saisie et n'affiche pas un numero existant. */}
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
      <div className="field-row">
        <label className="field">
          <span>{t("cp")}</span>
          <input
            value={valeurs.cp}
            // Comme au paiement : cinq chiffres, rien d'autre
            onChange={(e) => poser("cp")(e.target.value.replace(/\D/g, "").slice(0, 5))}
            inputMode="numeric"
            autoComplete="postal-code"
          />
        </label>
        <label className="field">
          <span>{t("ville")}</span>
          <input value={valeurs.city} onChange={poser("city")} autoComplete="address-level2" />
        </label>
      </div>

      {erreur && (
        <p className="field-error" role="alert">
          {erreur}
        </p>
      )}

      <div className="actions">
        <button className="btn btn-primary" type="submit" disabled={envoi}>
          <Check size={16} aria-hidden="true" /> {envoi ? t("processing") : t("save")}
        </button>
        <button className="btn btn-quiet" type="button" onClick={onAnnuler}>
          {t("cancel")}
        </button>
        <span className="muted" aria-live="polite">
          {rienAEnvoyer ? t("noChange") : t("nChanges", { n: Object.keys(changes).length })}
        </span>
      </div>
    </form>
  );
}

export default InfosForm;
