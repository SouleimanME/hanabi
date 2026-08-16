/** Ornements decoratifs : motifs traditionnels japonais dessines en SVG.
 *
 * Aucune image n'est telechargee : ces motifs sont generes, comme les visuels
 * produits de `ProductArt`. Trois avantages concrets - ils pesent quelques
 * centaines d'octets, restent nets a toutes les resolutions, et suivent le
 * theme clair/sombre puisqu'ils sont peints avec `currentColor`.
 *
 * Tous sont purement decoratifs, donc `aria-hidden` : un lecteur d'ecran ne
 * doit pas annoncer un blason.
 *
 * La frise seigaiha et la scene du Fuji vivaient ici. Elles ne servaient qu'au
 * pied de page, qui porte desormais l'embleme en filigrane : dessiner un
 * paysage n'appartient pas a cette direction, et deux motifs japonais empiles
 * sous un embleme japonais faisaient un motif de trop.
 */
import { memo } from "react";

import { LogoMark } from "./LogoMark.jsx";

/**
 * Filigrane de section : l'embleme de la maison, en tres grand et tres pale,
 * derriere le contenu.
 *
 * CE QUI A CHANGE, ET POURQUOI. Ce composant dessinait auparavant un blason
 * distinct - trois anneaux et six petales - qui coexistait avec le mitsudomoe
 * du logo. Deux emblemes pour une marque, c'en est un de trop : une identite
 * n'est pas une collection de symboles, c'est UN signe repete a des echelles
 * differentes jusqu'a devenir reconnaissable. Deux signes se diluent l'un
 * l'autre, et aucun des deux ne s'installe.
 *
 * Le pied de page appliquait deja ce traitement au mitsudomoe. Les sections le
 * partagent desormais, ce qui donne trois echelles d'un meme signe - la marque
 * de l'en-tete, le filigrane des sections, celui du pied de page - au lieu de
 * deux signes qui se disputent l'attention.
 *
 * Le nom `Kamon` est conserve : c'est bien un kamon (家紋), un blason de maison,
 * et les appelants n'ont pas a savoir quel trace il porte. Le renommer aurait
 * touche quatre fichiers pour ne rien changer.
 */
export const Kamon = memo(function Kamon({ size = 320 }) {
  return (
    // Le filigrane deborde volontairement du cadre de sa section. L'enveloppe
    // qui le rogne est indispensable : sans elle, le depassement s'ajoute a la
    // largeur du document et ouvre un defilement horizontal. La page glisse
    // alors sous l'en-tete et le grain de papier, tous deux en `position:
    // fixed`, ce qui donne l'impression que le site se dedouble.
    //
    // Le rognage est porte par le composant, et non par les sections qui
    // l'utilisent : d'une part aucun appelant ne peut oublier de s'en occuper,
    // d'autre part poser `overflow: hidden` sur une section rognerait aussi les
    // menus deroulants qu'elle contient.
    <span className="kamon-clip" aria-hidden="true">
      <span className="ornament kamon">
        <LogoMark size={size} />
      </span>
    </span>
  );
});
