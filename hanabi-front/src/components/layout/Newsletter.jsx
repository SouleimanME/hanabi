/** Inscription aux nouvelles series, dans le pied de page. */
import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { useT } from "../../i18n/context.jsx";
import { Newsletter as NewsletterApi } from "../../lib/api.js";
import { useAntiBot } from "../../hooks/useAntiBot.js";

export function Newsletter({ lang }) {
  const t = useT();
  const bot = useAntiBot("subscribe");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState(null);
  const [copie, setCopie] = useState(false);
  const [erreur, setErreur] = useState(null);
  const [envoi, setEnvoi] = useState(false);

  const envoyer = async (e) => {
    e.preventDefault();
    setErreur(null);
    if (!email.includes("@")) {
      setErreur(t("errEmail"));
      return;
    }
    setEnvoi(true);
    let preuve;
    try {
      preuve = await bot.getProof();
    } catch {
      setErreur(t("errAntibot"));
      setEnvoi(false);
      return;
    }
    try {
      const res = await NewsletterApi.subscribe(email.trim(), lang, preuve);
      setCode(res.code ?? "");
    } catch (err) {
      setErreur(err.message);
    } finally {
      setEnvoi(false);
    }
  };

  const copier = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopie(true);
    } catch {
      /* le code reste lisible et selectionnable */
    }
  };

  return (
    <section className="ft-news" aria-labelledby="ft-news-titre">
      <h2 id="ft-news-titre">{t("newsTitle")}</h2>
      {code !== null ? (
        <div className="ft-news-done" role="status">
          <p>
            <Check size={16} aria-hidden="true" /> {t("newsThanks")}
          </p>
          {code ? (
            <>
              <p>{t("newsCodeIntro")}</p>
              <button className="ft-code" onClick={copier} aria-label={t("newsCopy", { code })}>
                <span className="code">{code}</span>
                {copie ? <Check size={16} /> : <Copy size={16} />}
              </button>
            </>
          ) : (
            <p>{t("newsNoCode")}</p>
          )}
        </div>
      ) : (
        <form className="ft-news-form" onSubmit={envoyer} noValidate>
          <p>{t("newsSub")}</p>
          <div className="ft-news-row">
            <label className="sr-only" htmlFor="ft-news-email">
              {t("email")}
            </label>
            <input
              id="ft-news-email"
              type="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                setErreur(null);
              }}
              placeholder={t("notifyPh")}
              autoComplete="email"
              inputMode="email"
              autoCapitalize="none"
              spellCheck="false"
              aria-invalid={erreur ? true : undefined}
              aria-describedby={erreur ? "ft-news-err" : undefined}
            />
            <input {...bot.honeypotProps} />
            <button className="btn btn-on-lacquer" type="submit" disabled={envoi}>
              {envoi ? t("processing") : t("newsCta")}
            </button>
          </div>
          {erreur && (
            <p className="ft-news-err" id="ft-news-err" role="alert">
              {erreur}
            </p>
          )}
          <p className="ft-news-note">{t("newsNote")}</p>
        </form>
      )}
    </section>
  );
}
