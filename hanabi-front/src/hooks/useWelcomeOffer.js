import { useEffect, useState, useCallback } from "react";
import { useLocalStorageState } from "./useLocalStorageState.js";

/** Delai avant proposition spontanee, si rien d'autre ne l'a declenchee. */
const DELAY_MS = 20_000;

/** Part de la page parcourue au-dela de laquelle l'interet est manifeste. */
const SCROLL_RATIO = 0.5;

/**
 * Decide quand proposer l'offre de bienvenue.
 *
 * Trois declencheurs, au premier des trois :
 *   - vingt secondes passees sur le site ;
 *   - la moitie de la page parcourue ;
 *   - le pointeur qui sort par le haut de la fenetre, signe d'un depart.
 *
 * Aucun ne se produit au chargement : une fenetre qui s'ouvre avant qu'on ait
 * vu la boutique fait fuir plus qu'elle ne recrute. La reponse - inscription
 * comme refus - est conservee, et la proposition ne revient pas.
 *
 * @param {boolean} eligible faux pendant la commande, ou pour un client connecte
 */
export function useWelcomeOffer(eligible) {
  const [answered, setAnswered] = useLocalStorageState("welcome", null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    // Entrer dans le tunnel de commande referme la proposition sans la
    // consommer : elle reviendra ailleurs. Ouverte, elle resterait affichee
    // par-dessus le formulaire de paiement, exactement la ou l'on ne veut
    // detourner personne.
    if (!eligible) {
      setOpen(false);
      return;
    }
    if (answered || open) return;

    const show = () => setOpen(true);

    const timer = setTimeout(show, DELAY_MS);

    const onScroll = () => {
      const height = document.documentElement.scrollHeight - window.innerHeight;
      if (height > 0 && window.scrollY / height > SCROLL_RATIO) show();
    };

    // `clientY <= 0` : le pointeur sort par le haut, vers la barre d'adresse ou
    // les onglets. Sortir par les cotes ou par le bas ne signifie rien.
    const onLeave = (e) => {
      if (e.clientY <= 0) show();
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    document.addEventListener("mouseleave", onLeave);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("scroll", onScroll);
      document.removeEventListener("mouseleave", onLeave);
    };
  }, [eligible, answered, open]);

  /** Enregistre la reponse sans refermer : l'inscription doit rester acquise
   *  meme si le panneau est quitte par un changement de page plutot que par sa
   *  croix, sans quoi l'offre serait reproposee a quelqu'un qui l'a acceptee.
   *  @param {"subscribed"|"dismissed"} outcome */
  const remember = useCallback((outcome) => setAnswered(outcome), [setAnswered]);

  /** Enregistre la reponse et referme. Fermer sans s'inscrire compte comme un
   *  refus : reproposer a chaque page serait du harcelement. */
  const answer = useCallback(
    (outcome) => {
      remember(outcome);
      setOpen(false);
    },
    [remember],
  );

  return { open, answer, remember };
}
