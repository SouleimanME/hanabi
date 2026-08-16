/** Pied de page : identite, raccourcis catalogue et acces aux pages legales.
 *
 * C'est la seule surface du site qui reste en laque quand la boutique est sur
 * papier : la page s'arrete, et dessous il y a l'urushi brut. Le pied n'est donc
 * pas un bas de page, c'est le support sur lequel tout le reste etait pose.
 *
 * Deux ornements y vivaient, herites de l'identite precedente : une frise de
 * vagues seigaiha et une scene de mont Fuji. Ils dessinaient un paysage, ce que
 * cette direction ne fait jamais - et deux motifs japonais empiles sous un
 * embleme japonais, c'est un motif de trop. A leur place, l'embleme lui-meme,
 * agrandi jusqu'a deborder et pose si bas dans le contraste qu'il se lit comme
 * une trace dans la matiere plutot que comme une image.
 */
import { useT } from "../../i18n/context.jsx";
import { LogoMark } from "../brand/LogoMark.jsx";

const LEGAL_PAGES = ["mentions", "cgv", "confidentialite", "cookies"];
const SHOP_CATEGORIES = ["Compagnons", "Tradition", "Collection"];

export function Footer({ onGoCategory, onOpenLegal }) {
  const t = useT();

  return (
    <footer className="ft">
      {/* Filigrane : l'embleme dans la laque, rogne par le bord droit. Il est
          decoratif au sens strict, donc masque aux lecteurs d'ecran. */}
      <div className="ft-filigrane" aria-hidden="true">
        <LogoMark size={520} />
      </div>

      <div className="ft-in">
        <div className="ft-marque">
          <div className="logo ft-logo">
            <LogoMark size={30} />
            HANABI<span className="logo-jp">花火</span>
          </div>
          <p className="ft-tag">{t("ftTag")}</p>
        </div>

        <div className="ft-cols">
          <div>
            <h4>{t("shop")}</h4>
            {SHOP_CATEGORIES.map((c) => (
              <button key={c} className="ft-link" onClick={() => onGoCategory(c)}>
                {t("cat_" + c)}
              </button>
            ))}
          </div>
          <div>
            <h4>{t("help")}</h4>
            <span>{t("lLivraison")}</span>
            <span>{t("lRetours")}</span>
            <span>{t("lDropTrack")}</span>
            <span>{t("lContact")}</span>
          </div>
          <div>
            <h4>{t("maisonCol")}</h4>
            <span>{t("lStory")}</span>
            <span>{t("lAteliers")}</span>
            <span>{t("lJournal")}</span>
          </div>
        </div>
      </div>

      <div className="ft-legal">
        <div className="ft-legal-in">
          <span>© {new Date().getFullYear()} Hanabi</span>
          <div className="ft-legal-links">
            {LEGAL_PAGES.map((page) => (
              <button key={page} className="ft-legal-link" onClick={() => onOpenLegal(page)}>
                {t("legal_" + page)}
              </button>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}
