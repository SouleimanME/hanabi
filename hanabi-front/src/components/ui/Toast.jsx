/** Notification breve, en bas d'ecran.
 *
 * Le noeud reste monte en permanence et joue sur l'opacite : cela permet la
 * transition de sortie, et `aria-live="polite"` annonce le message aux
 * lecteurs d'ecran sans interrompre la lecture en cours.
 */
import { Check } from "lucide-react";

export function Toast({ message }) {
  return (
    <div className={"toast" + (message ? " show" : "")} aria-live="polite">
      <Check size={15} strokeWidth={3} />
      {message}
    </div>
  );
}
