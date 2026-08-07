import { useCallback, useEffect, useRef } from "react";
import { solveChallenge } from "../lib/antibot.js";

/** Marge de securite avant expiration : on prefere refaire une preuve que se
 *  faire refuser parce que l'horloge du client derive de quelques secondes. */
const EXPIRY_MARGIN_MS = 30_000;

/**
 * Prepare, entretient et fournit la preuve anti-robot d'un formulaire.
 *
 * La preuve est calculee des le montage, pendant que l'utilisateur saisit ses
 * informations : au moment de valider, elle est prete et la latence percue est
 * nulle. Une nouvelle preuve est relancee en arriere-plan apres chaque usage,
 * car le serveur refuse un defi deja consomme.
 *
 * `getProof` couvre les deux cas ou la preuve en cache ne convient pas :
 *   - trop vieille (defi expire cote serveur) : on en refait une ;
 *   - trop fraiche : le serveur exige un delai minimal entre l'affichage du
 *     formulaire et son envoi. Quelqu'un qui laisse le navigateur remplir les
 *     champs puis clique aussitot serait refuse a tort, donc on patiente le
 *     temps restant plutot que de laisser partir une requete vouee a l'echec.
 *
 * @param {"register"|"login"|"notify"|"review"} purpose
 * @returns {{getProof: () => Promise<object>, honeypotProps: object}}
 */
export function useAntiBot(purpose) {
  const cache = useRef(null);
  const pending = useRef(null);
  const alive = useRef(true);
  const honeypot = useRef(null);

  const solve = useCallback(() => {
    // Une seule resolution a la fois : deux appels concurrents partagent la
    // meme promesse plutot que de calculer deux preuves pour rien.
    if (pending.current) return pending.current;
    pending.current = solveChallenge(purpose)
      .then((proof) => {
        if (alive.current) cache.current = proof;
        return proof;
      })
      .finally(() => {
        pending.current = null;
      });
    return pending.current;
  }, [purpose]);

  useEffect(() => {
    alive.current = true;
    solve().catch(() => {
      /* API injoignable : getProof retentera au moment de l'envoi. */
    });
    return () => {
      alive.current = false;
    };
  }, [solve]);

  const getProof = useCallback(async () => {
    let proof = cache.current;

    const expired = (p) => Date.now() - p.solvedAt > p.ttlSeconds * 1000 - EXPIRY_MARGIN_MS;
    if (!proof || expired(proof)) {
      proof = await solve();
    }

    // Le defi ne servira qu'une fois : on le retire du cache et on en prepare
    // un autre pour la tentative suivante (mot de passe errone, par exemple).
    cache.current = null;
    solve().catch(() => {});

    const elapsed = Date.now() - proof.fields.issued_at * 1000;
    const remaining = proof.minSeconds * 1000 - elapsed;
    if (remaining > 0) {
      await new Promise((resolve) => setTimeout(resolve, remaining + 100));
    }

    // Ce que le champ piege contient au moment de l'envoi. Une personne ne peut
    // pas l'avoir rempli : il est sorti de l'ecran et du parcours de tabulation.
    // Le transmettre est indispensable - un pot de miel dont la valeur n'arrive
    // jamais au serveur ne detecte rien.
    return { ...proof.fields, honeypot: honeypot.current?.value ?? "" };
  }, [solve]);

  return {
    getProof,
    /** A etaler sur un champ texte piege, que seuls les robots rempliront. */
    honeypotProps: {
      ref: honeypot,
      type: "text",
      // Un nom plausible : c'est justement ce qui attire les robots.
      name: "website",
      tabIndex: -1,
      autoComplete: "off",
      "aria-hidden": true,
      className: "honeypot",
    },
  };
}
