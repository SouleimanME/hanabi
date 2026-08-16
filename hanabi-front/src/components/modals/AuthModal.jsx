/** Connexion et inscription.
 *
 * L'inscription est decoupee en deux etapes : un formulaire unique de douze
 * champs fait fuir. La validation est faite champ par champ cote client pour
 * le confort, et refaite cote serveur pour la securite.
 */
import { useState } from "react";
import {
  X,
  MailCheck,
  ArrowLeft,
  Check,
  Lock,
  Truck,
  RotateCcw,
  Sparkles,
  ShieldCheck,
} from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import { DatePicker } from "../ui/DatePicker.jsx";
import { PhoneField } from "../ui/PhoneField.jsx";
import { PwField, PwStrength, PwChecklist } from "../ui/PasswordField.jsx";
import { isPasswordStrong } from "../../lib/password.js";
import { useAntiBot } from "../../hooks/useAntiBot.js";
import { useFocusTrap } from "../../hooks/useFocusTrap.js";
import { Auth } from "../../lib/api.js";

/** Ce que le compte apporte, montre a l'inscription.
 *
 * Un formulaire de douze champs sans contrepartie visible fait abandonner. Ces
 * trois lignes rappellent ce qu'on obtient en echange de l'effort. */
const PERKS = [
  { icon: Truck, key: "perkShip" },
  { icon: RotateCcw, key: "perkOrders" },
  { icon: Sparkles, key: "perkDrop" },
];

export function AuthModal({ onClose, onLogin, onSignup }) {
  const t = useT();
  const [mode, setMode] = useState("login");
  // La preuve anti-robot est calculee des l'ouverture, pendant la saisie : au
  // moment de valider, elle est prete et l'attente percue est nulle.
  const antibot = useAntiBot(mode === "signup" ? "register" : "login");
  const trapRef = useFocusTrap();
  const [civility, setCivility] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [pwConfirm, setPwConfirm] = useState("");
  const [birthdate, setBirthdate] = useState("");
  const [phone, setPhone] = useState("");
  const [addr, setAddr] = useState("");
  const [addrExtra, setAddrExtra] = useState("");
  const [cp, setCp] = useState("");
  const [city, setCity] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState(1);
  // Confirmation d'envoi du lien de reinitialisation. Un booleen suffit :
  // l'ecran ne revient jamais en arriere depuis cet etat.
  const [oubliEnvoye, setOubliEnvoye] = useState(false);

  const resetSignup = () => {
    setStep(1);
    setCivility("");
    setName("");
    setEmail("");
    setPw("");
    setPwConfirm("");
    setBirthdate("");
    setPhone("");
    setAddr("");
    setAddrExtra("");
    setCp("");
    setCity("");
    setErr(null);
  };

  const validateStep1 = () => {
    if (!civility) return t("errCivility");
    if (name.trim().length < 2) return t("errName");
    const parts = birthdate.split("-");
    if (!parts[0] || !parts[1] || !parts[2] || parts.some((p) => p === ""))
      return t("errBirthdate");
    if (Math.floor((Date.now() - new Date(birthdate)) / 31557600000) < 16) return t("errAge");
    return null;
  };

  const validatePw = (v) => (isPasswordStrong(v) ? null : t("errPwWeak"));

  const submit = async () => {
    setErr(null);

    if (mode === "forgot") {
      if (!email.includes("@")) return setErr(t("errEmail"));
      setBusy(true);
      try {
        await Auth.forgotPassword(email.trim());
      } catch (e) {
        // Une panne reseau se dit ; un compte inconnu, non. Le serveur repond
        // succes dans les deux cas a dessein, et distinguer ici les deux
        // situations reintroduirait cote client la fuite qu'il refuse.
        if (e.network) {
          setBusy(false);
          return setErr(e.message);
        }
      }
      setBusy(false);
      setOubliEnvoye(true);
      return;
    }

    if (mode === "signup") {
      if (step === 1) {
        const e = validateStep1();
        if (e) return setErr(e);
        setStep(2);
        return;
      }
      if (!email.includes("@")) return setErr(t("errEmail"));
      const pwErr = validatePw(pw);
      if (pwErr) return setErr(pwErr);
      if (pw !== pwConfirm) return setErr(t("errPwMatch"));
      if (phone.replace(/\D/g, "").length < 9) return setErr(t("errPhone"));
      if (!addr.trim()) return setErr(t("required", { f: t("adresse") }));
      if (!cp.trim()) return setErr(t("required", { f: t("cp") }));
      if (!city.trim()) return setErr(t("required", { f: t("ville") }));
    } else {
      if (!email.includes("@")) return setErr(t("errEmail"));
      if (!pw) return setErr(t("errPw"));
    }
    setBusy(true);
    let e;
    try {
      const proof = await antibot.getProof();
      e =
        mode === "signup"
          ? await onSignup({
              name: name.trim(),
              email: email.trim(),
              password: pw,
              civility,
              birthdate,
              phone: phone.trim(),
              addr: addr.trim(),
              addr_extra: addrExtra.trim(),
              cp: cp.trim(),
              city: city.trim(),
              antibot: proof,
            })
          : await onLogin({ email: email.trim(), password: pw, antibot: proof });
    } catch {
      // La preuve n'a pas pu etre obtenue : API injoignable, le plus souvent.
      e = t("errAntibot");
    }
    setBusy(false);
    if (e) setErr(e);
    else onClose();
  };

  // Un titre par mode. Le ternaire d'origine ne connaissait que deux etats et
  // affichait « Creer un compte » sur le formulaire de mot de passe oublie.
  const TITRES = {
    login: t("signin"),
    signup: t("createAccount"),
    forgot: t("forgotTitle"),
  };

  const CIVILITIES = [
    { value: "M", label: t("civM") },
    { value: "F", label: t("civF") },
    { value: "N", label: t("civN") },
  ];
  const confirmOk = pwConfirm.length > 0 && pw === pwConfirm;

  return (
    <div className="modal-scrim" onClick={onClose}>
      <div
        ref={trapRef}
        className="modal modal-tall"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={TITRES[mode]}
      >
        <button className="icon-btn modal-x" onClick={onClose} aria-label="Fermer">
          <X size={18} />
        </button>
        <h2 className="modal-h">{TITRES[mode]}</h2>
        {mode !== "forgot" && (
          <div className="tabs">
            <button
              className={mode === "login" ? "on" : ""}
              onClick={() => {
                setMode("login");
                resetSignup();
              }}
            >
              {t("signin")}
            </button>
            <button
              className={mode === "signup" ? "on" : ""}
              onClick={() => {
                setMode("signup");
                setErr(null);
              }}
            >
              {t("signup")}
            </button>
          </div>
        )}

        {mode === "signup" && (
          <div className="signup-steps">
            <div className={"step-dot" + (step === 1 ? " on" : "")} />
            <div className="step-line" />
            <div className={"step-dot" + (step === 2 ? " on" : "")} />
          </div>
        )}

        <div className="modal-scroll">
          {mode === "signup" && step === 1 && (
            <>
              <p className="step-label">{t("stepIdentity")}</p>
              <div className="civ-row">
                {CIVILITIES.map((c) => (
                  <button
                    key={c.value}
                    type="button"
                    className={"civ-btn" + (civility === c.value ? " on" : "")}
                    onClick={() => setCivility(c.value)}
                  >
                    {c.label}
                  </button>
                ))}
              </div>
              <label className="field">
                <span>{t("fullName")}</span>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Prénom Nom"
                  autoComplete="name"
                />
              </label>
              <DatePicker value={birthdate} onChange={setBirthdate} />
              <ul className="perks">
                {PERKS.map(({ icon: Icon, key }) => (
                  <li key={key}>
                    <Icon size={15} /> {t(key)}
                  </li>
                ))}
              </ul>
            </>
          )}

          {mode === "signup" && step === 2 && (
            <>
              <p className="step-label">{t("stepContact")}</p>
              <PhoneField label={t("phone")} onChange={setPhone} />
              <label className="field">
                <span>{t("adresse")}</span>
                <input
                  value={addr}
                  onChange={(e) => setAddr(e.target.value)}
                  placeholder={t("addrPh")}
                  autoComplete="address-line1"
                />
              </label>
              <label className="field">
                <span>{t("addrExtra")}</span>
                <input
                  value={addrExtra}
                  onChange={(e) => setAddrExtra(e.target.value)}
                  placeholder={t("addrExtraPh")}
                  autoComplete="address-line2"
                />
              </label>
              <div className="row2">
                <label className="field">
                  <span>{t("cp")}</span>
                  <input
                    value={cp}
                    onChange={(e) => setCp(e.target.value)}
                    inputMode="numeric"
                    autoComplete="postal-code"
                  />
                </label>
                <label className="field">
                  <span>{t("ville")}</span>
                  <input
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    autoComplete="address-level2"
                  />
                </label>
              </div>
              <label className="field">
                <span>{t("email")}</span>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="toi@exemple.fr"
                  autoComplete="email"
                  inputMode="email"
                  autoCapitalize="none"
                  spellCheck="false"
                />
              </label>
              <PwField
                label={t("password")}
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                autoComplete="new-password"
              />
              {pw && (
                <>
                  <PwStrength value={pw} />
                  <PwChecklist value={pw} />
                </>
              )}
              <PwField
                label={t("pwConfirmLabel")}
                value={pwConfirm}
                onChange={(e) => setPwConfirm(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && submit()}
                autoComplete="new-password"
                invalid={pwConfirm.length > 0 && pw !== pwConfirm}
              />
              {pwConfirm && (
                <div className={"pw-match" + (confirmOk ? " ok" : "")}>
                  {confirmOk ? (
                    <>
                      <Check size={12} strokeWidth={3} /> {t("pwMatchOk")}
                    </>
                  ) : (
                    t("pwMatchErr")
                  )}
                </div>
              )}
            </>
          )}

          {mode === "login" && (
            <>
              <label className="field">
                <span>{t("email")}</span>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="toi@exemple.fr"
                  autoComplete="username"
                  inputMode="email"
                  autoCapitalize="none"
                  spellCheck="false"
                />
              </label>
              <PwField
                label={t("password")}
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && submit()}
                autoComplete="current-password"
              />
              {/* Sous le champ, et non dans un coin : c'est ici qu'on regarde
                  au moment precis ou l'on se rend compte qu'on a oublie. */}
              <button className="lien-oubli" onClick={() => setMode("forgot")}>
                {t("forgotLink")}
              </button>
            </>
          )}

          {mode === "forgot" &&
            (oubliEnvoye ? (
              /* Message volontairement IDENTIQUE que le compte existe ou non :
                 confirmer l'envoi seulement pour les adresses connues ferait de
                 cette fenetre un detecteur d'adresses, exactement ce que le
                 serveur refuse en repondant toujours succes. */
              <div className="oubli-envoye" role="status">
                <MailCheck size={22} />
                <p>{t("forgotSentTitle")}</p>
                <p className="muted small">{t("forgotSentBody")}</p>
              </div>
            ) : (
              <>
                <p className="modal-intro">{t("forgotBody")}</p>
                <label className="field">
                  <span>{t("email")}</span>
                  <input
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && submit()}
                    placeholder="toi@exemple.fr"
                    autoComplete="username"
                    inputMode="email"
                    autoCapitalize="none"
                    spellCheck="false"
                  />
                </label>
              </>
            ))}

          {/* Champ piege : hors ecran et hors tabulation, seuls les robots le
              remplissent. Voir hooks/useAntiBot.js. */}
          <input {...antibot.honeypotProps} />

          {err && (
            <div className="form-err" role="alert">
              {err}
            </div>
          )}

          <div className="modal-actions">
            {mode === "forgot" && (
              <button
                className="btn-ghost"
                onClick={() => {
                  setMode("login");
                  setOubliEnvoye(false);
                  setErr(null);
                }}
              >
                <ArrowLeft size={15} /> {t("back")}
              </button>
            )}
            {mode === "signup" && step === 2 && (
              <button
                className="btn-ghost"
                onClick={() => {
                  setStep(1);
                  setErr(null);
                }}
              >
                <ArrowLeft size={15} /> {t("back")}
              </button>
            )}
            {/* Le bouton disparait une fois le lien envoye : il n'y a plus
                rien a soumettre, et le laisser inviterait a le renvoyer en
                boucle. */}
            {!(mode === "forgot" && oubliEnvoye) && (
              <button className="btn-primary grow" onClick={submit} disabled={busy}>
                {busy
                  ? "…"
                  : mode === "forgot"
                    ? t("forgotSubmit")
                    : mode === "login"
                      ? t("doLogin")
                      : step === 1
                        ? `${t("next")} →`
                        : t("doSignup")}
              </button>
            )}
          </div>
        </div>

        {mode === "signup" && (
          <p className="modal-note">
            <ShieldCheck size={12} /> {t("privacyNote")}
          </p>
        )}
        <p className="modal-note">
          <Lock size={12} /> {t("demoNote")}
        </p>
        {/* Acces au back-office, pour qui veut voir l'envers du site sans avoir
            a demander d'identifiants. Affiche seulement en connexion : a
            l'inscription, la place revient aux arguments du compte client. Ce
            compte est bride en lecture seule cote serveur. */}
        {mode === "login" && (
          <p className="modal-note">
            <ShieldCheck size={12} /> {t("adminNote")}
          </p>
        )}
      </div>
    </div>
  );
}
