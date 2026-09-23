/** Connexion, inscription en deux etapes, mot de passe oublie. */
import { useState } from "react";
import { X, MailCheck, ArrowLeft, Check } from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import { DatePicker } from "../ui/DatePicker.jsx";
import { PhoneField } from "../ui/PhoneField.jsx";
import { PwField, PwStrength, PwChecklist } from "../ui/PasswordField.jsx";
import { isPasswordStrong } from "../../lib/password.js";
import { useAntiBot } from "../../hooks/useAntiBot.js";
import { useFocusTrap } from "../../hooks/useFocusTrap.js";
import { Auth } from "../../lib/api.js";

export function AuthModal({ onClose, onLogin, onSignup }) {
  const t = useT();
  const [mode, setMode] = useState("login");
  // La preuve anti-robot se calcule pendant la saisie : elle est prete a l'envoi
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
    if (parts.length !== 3 || parts.some((p) => p === "")) return t("errBirthdate");
    if (Math.floor((Date.now() - new Date(birthdate)) / 31557600000) < 16) return t("errAge");
    return null;
  };

  const submit = async (e) => {
    e.preventDefault();
    setErr(null);

    if (mode === "forgot") {
      if (!email.includes("@")) return setErr(t("errEmail"));
      setBusy(true);
      try {
        await Auth.forgotPassword(email.trim());
      } catch (error) {
        // Une panne reseau se dit ; un compte inconnu, non : le serveur repond
        // succes dans les deux cas, et l'ecran doit faire de meme.
        if (error.network) {
          setBusy(false);
          return setErr(error.message);
        }
      }
      setBusy(false);
      setOubliEnvoye(true);
      return;
    }

    if (mode === "signup") {
      if (step === 1) {
        const probleme = validateStep1();
        if (probleme) return setErr(probleme);
        setStep(2);
        return;
      }
      if (!email.includes("@")) return setErr(t("errEmail"));
      if (!isPasswordStrong(pw)) return setErr(t("errPwWeak"));
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
    let probleme;
    try {
      const proof = await antibot.getProof();
      probleme =
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
      probleme = t("errAntibot");
    }
    setBusy(false);
    if (probleme) setErr(probleme);
    else onClose();
  };

  const titres = { login: t("signin"), signup: t("createAccount"), forgot: t("forgotTitle") };
  const civilites = [
    { value: "M", label: t("civM") },
    { value: "F", label: t("civF") },
    { value: "N", label: t("civN") },
  ];
  const confirmOk = pwConfirm.length > 0 && pw === pwConfirm;

  const libelleEnvoi = busy
    ? t("processing")
    : mode === "forgot"
      ? t("forgotSubmit")
      : mode === "login"
        ? t("doLogin")
        : step === 1
          ? t("next")
          : t("doSignup");

  return (
    <div className="modal-layer">
      <div className="scrim" data-open="true" onClick={onClose} aria-hidden="true" />
      <div
        ref={trapRef}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-titre"
      >
        <div className="sheet-head">
          <h2 id="auth-titre">{titres[mode]}</h2>
          <button className="icon-btn" onClick={onClose} aria-label={t("close")}>
            <X size={20} />
          </button>
        </div>

        {mode !== "forgot" && (
          <div className="tabs" role="tablist" aria-label={titres[mode]}>
            <button
              role="tab"
              aria-selected={mode === "login"}
              onClick={() => {
                setMode("login");
                resetSignup();
              }}
            >
              {t("signin")}
            </button>
            <button
              role="tab"
              aria-selected={mode === "signup"}
              onClick={() => {
                setMode("signup");
                setErr(null);
              }}
            >
              {t("signup")}
            </button>
          </div>
        )}

        <form className="modal-body form-stack" onSubmit={submit} noValidate>
          {mode === "signup" && (
            <p className="step">{step === 1 ? t("stepIdentity") : t("stepContact")}</p>
          )}

          {mode === "signup" && step === 1 && (
            <>
              <fieldset className="field">
                <legend>{t("civility")}</legend>
                <div className="chips">
                  {civilites.map((c) => (
                    <button
                      key={c.value}
                      type="button"
                      className="chip"
                      aria-pressed={civility === c.value}
                      onClick={() => setCivility(c.value)}
                    >
                      {c.label}
                    </button>
                  ))}
                </div>
              </fieldset>
              <label className="field">
                <span>{t("fullName")}</span>
                <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" />
              </label>
              <DatePicker value={birthdate} onChange={setBirthdate} />
            </>
          )}

          {mode === "signup" && step === 2 && (
            <>
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
              <div className="field-row">
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
                autoComplete="new-password"
                invalid={pwConfirm.length > 0 && pw !== pwConfirm}
              />
              {pwConfirm && (
                <p className={confirmOk ? "field-hint" : "field-error"} aria-live="polite">
                  {confirmOk && <Check size={12} strokeWidth={3} aria-hidden="true" />}{" "}
                  {confirmOk ? t("pwMatchOk") : t("pwMatchErr")}
                </p>
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
                autoComplete="current-password"
              />
              <div>
                <button type="button" className="link" onClick={() => setMode("forgot")}>
                  {t("forgotLink")}
                </button>
              </div>
            </>
          )}

          {mode === "forgot" &&
            (oubliEnvoye ? (
              /* Meme message que le compte existe ou non */
              <div className="notice" role="status">
                <MailCheck size={20} aria-hidden="true" />
                <div>
                  <p>{t("forgotSentTitle")}</p>
                  <p className="muted">{t("forgotSentBody")}</p>
                </div>
              </div>
            ) : (
              <>
                <p className="muted">{t("forgotBody")}</p>
                <label className="field">
                  <span>{t("email")}</span>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    autoComplete="username"
                    inputMode="email"
                    autoCapitalize="none"
                    spellCheck="false"
                  />
                </label>
              </>
            ))}

          <input {...antibot.honeypotProps} />

          {err && (
            <p className="notice notice-error" role="alert">
              {err}
            </p>
          )}

          <div className="actions">
            {mode === "forgot" && (
              <button
                type="button"
                className="btn btn-quiet"
                onClick={() => {
                  setMode("login");
                  setOubliEnvoye(false);
                  setErr(null);
                }}
              >
                <ArrowLeft size={16} aria-hidden="true" /> {t("back")}
              </button>
            )}
            {mode === "signup" && step === 2 && (
              <button
                type="button"
                className="btn btn-quiet"
                onClick={() => {
                  setStep(1);
                  setErr(null);
                }}
              >
                <ArrowLeft size={16} aria-hidden="true" /> {t("back")}
              </button>
            )}
            {!(mode === "forgot" && oubliEnvoye) && (
              <button className="btn btn-primary btn-grow" type="submit" disabled={busy}>
                {libelleEnvoi}
              </button>
            )}
          </div>

          {mode === "signup" && <p className="demo-note">{t("privacyNote")}</p>}
          {mode === "login" && (
            <div className="demo-accounts">
              <p>{t("demoNote")}</p>
              <p>{t("adminNote")}</p>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
