/** Compte a rebours jusqu'a la prochaine serie hebdomadaire.
 *
 * Le nom du composant et la classe CSS gardent le terme « drop » : ce sont des
 * identifiants internes, que renommer n'apporterait rien au visiteur. Le
 * vocabulaire visible, lui, parle de serie et de selection. */
import { useState, useEffect } from "react";
import { useT } from "../../i18n/context.jsx";
import { nextDropDate } from "../../lib/drop.js";

export function DropCountdown() {
  const t = useT();
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const diff = Math.max(0, nextDropDate().getTime() - now);
  const d = Math.floor(diff / 86400000),
    h = Math.floor(diff / 3600000) % 24,
    m = Math.floor(diff / 60000) % 60,
    s = Math.floor(diff / 1000) % 60;
  const pad = (n) => String(n).padStart(2, "0");
  return (
    <div className="dropbar">
      <span className="dropbar-l">花火 · {t("nextDrop")}</span>
      <span className="dropbar-t mono">
        {d}
        {t("dd")} {pad(h)}
        {t("hh")} {pad(m)}
        {t("mm")} {pad(s)}
        {t("ss")}
      </span>
    </div>
  );
}
