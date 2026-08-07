/** Offre de bienvenue : une adresse contre une remise sur la premiere serie.
 *
 * Panneau d'angle plutot que fenetre modale : il ne voile pas la boutique, ne
 * prend pas le focus et n'interrompt pas la lecture. On peut l'ignorer, ce qui
 * est precisement ce qui le rend acceptable - et il est de toute facon propose
 * apres coup, jamais au chargement (voir hooks/useWelcomeOffer.js).
 *
 * Le consentement est explicite et le contenu de l'engagement est ecrit a cote
 * du champ, pas dans une page qu'il faudrait aller chercher.
 */
import { useState } from "react";
import { X, Check, Copy, Sparkles } from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import { Newsletter } from "../../lib/api.js";
import { useAntiBot } from "../../hooks/useAntiBot.js";

export function WelcomeOffer({ lang, onAnswer, onRemember }) {
  const t = useT();
  const bot = useAntiBot("subscribe");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState(null);
  const [copied, setCopied] = useState(false);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!email.includes("@")) {
      setErr(t("errEmail"));
      return;
    }
    setBusy(true);
    let proof;
    try {
      proof = await bot.getProof();
    } catch {
      setErr(t("errAntibot"));
      setBusy(false);
      return;
    }
    try {
      const res = await Newsletter.subscribe(email.trim(), lang, proof);
      // L'inscription vaut meme sans code : le serveur ne l'annonce que si
      // l'offre existe reellement.
      setCode(res.code);
      setErr(null);
      onRemember("subscribed");
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
    } catch {
      /* presse-papiers refuse : le code reste lisible et selectionnable */
    }
  };

  return (
    <aside className="welcome" role="complementary" aria-label={t("welcomeTitle")}>
      <button
        className="welcome-x icon-btn"
        onClick={() => onAnswer(code ? "subscribed" : "dismissed")}
        aria-label={t("close")}
      >
        <X size={16} />
      </button>

      {code !== null ? (
        <div className="welcome-done">
          <div className="welcome-h">
            <Check size={16} strokeWidth={3} /> {t("welcomeThanks")}
          </div>
          {code ? (
            <>
              <p className="muted small">{t("welcomeCodeIntro")}</p>
              <button className="welcome-code" onClick={copy}>
                <span className="mono">{code}</span>
                {copied ? <Check size={14} strokeWidth={3} /> : <Copy size={14} />}
              </button>
            </>
          ) : (
            <p className="muted small">{t("welcomeNoCode")}</p>
          )}
        </div>
      ) : (
        <>
          <div className="welcome-h">
            <Sparkles size={16} /> {t("welcomeTitle")}
          </div>
          <p className="welcome-sub">{t("welcomeSub")}</p>
          <div className="welcome-row">
            <input
              type="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                setErr(null);
              }}
              onKeyDown={(e) => e.key === "Enter" && submit()}
              placeholder={t("notifyPh")}
              aria-label={t("email")}
              autoComplete="email"
              inputMode="email"
              autoCapitalize="none"
            />
            <input {...bot.honeypotProps} />
            <button className="btn-primary sm" onClick={submit} disabled={busy}>
              {busy ? t("processing") : t("welcomeCta")}
            </button>
          </div>
          {err && <div className="form-err">{err}</div>}
          <p className="welcome-note muted">{t("welcomeNote")}</p>
        </>
      )}
    </aside>
  );
}
