/** Embleme Hanabi : un torii devant le soleil, une fleur de cerisier.
 *
 * Les motifs sont assumes comme des cliches - ce sont les deux images que le
 * monde entier associe au Japon, et un embleme de boutique doit etre reconnu
 * en une fraction de seconde, pas decode.
 *
 * Ce qui separe un cliche reussi d'un cliche rate n'est pas le choix des
 * motifs mais leur nombre. L'emblema precedent en empilait cinq - torii, pleine
 * lune, deux katanas croises, sakura - sur une centaine de formes et huit
 * couleurs : illisible sous quarante pixels. Ici il y en a deux, poses sur un
 * disque, dans un anneau.
 *
 * SUR LA COULEUR. Une premiere version etait monochrome, tracee en
 * `currentColor`. C'etait defendable et c'etait terne : un torii vermillon et
 * un cerisier rose sont deux emblemes de saisons differentes, les confondre
 * dans une seule encre revenait a jeter la moitie du sujet. Chaque element a
 * donc sa teinte, prise a la palette du site.
 *
 * Elles restent surchargeables par variables CSS : le back-office peut ainsi
 * ramener l'emblema a son or sans qu'on maintienne un second fichier.
 *
 * DEUX REGLES TENUES. Le torii est symetrique, le sakura ne l'est pas : la
 * symetrie donne l'assise, l'asymetrie donne la vie - c'est le fukinsei de
 * l'esthetique japonaise. Et rien ne descend sous dix unites de large dans le
 * repere de 100 : en dessous, un detail se referme a la taille d'un favicon et
 * ne fait plus que salir la forme.
 */

/** Petale de sakura, pointe vers le haut, hauteur 12 dans le repere de 100.
 *
 *  L'echancrure au sommet n'est pas un ornement : c'est elle qui distingue un
 *  cerisier d'un prunier. Sans elle on dessine un ume, qui est une autre fleur
 *  et une autre saison. */
const PETALE =
  "M0 5C-4.6 3.6-5.9 -0.4-4.4 -3.5C-3.6 -5.2-2 -6.3-1 -7.3" +
  "L0 -5.9L1 -7.3C2 -6.3 3.6 -5.2 4.4 -3.5C5.9 -0.4 4.6 3.6 0 5Z";

const PETALES = [0, 72, 144, 216, 288];

/** Etamines. Un cerisier en porte une trentaine, longues et debordant largement
 *  de la corolle ; c'est ce debordement qui le rend reconnaissable de loin.
 *  Six suffisent a le suggerer, au-dela elles se collent les unes aux autres
 *  des qu'on reduit. */
const ETAMINES = [-58, -22, 12, 48, 96, 148];

export function LogoMark({ size = 34, title }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : "true"}
      style={{ flexShrink: 0, display: "block" }}
    >
      {/* Anneau d'enfermement, comme sur un kamon. Il donne un bord franc a
          l'emblema, ce qui vaut mieux qu'une silhouette qui s'effiloche sur un
          fond dont on ne maitrise pas la couleur. */}
      <circle cx="50" cy="50" r="45" stroke="var(--lm-anneau, #E0382A)" strokeWidth="3.4" />

      {/* Le soleil, en retrait. A vingt pour cent il se lit comme une matiere
          et non comme un second motif : c'est un fond, pas un element. */}
      <circle cx="50" cy="45" r="27" fill="var(--lm-soleil, #E8A83A)" opacity="0.22" />

      <g fill="var(--lm-torii, #E0382A)">
        {/* Kasagi, le linteau superieur. Ses extremites remontent : c'est ce
            galbe qui fait lire un torii plutot qu'un portique. */}
        <path d="M17 29.5Q50 23 83 29.5L83 35Q50 28.5 17 35Z" />

        {/* Gakuzuka, le montant central entre les deux linteaux. Minuscule,
            mais son absence fait immediatement faux. */}
        <rect x="47.6" y="34" width="4.8" height="7" />

        {/* Nuki, le linteau inferieur. Il depasse des piliers de chaque cote,
            comme sur un vrai torii. */}
        <rect x="25" y="40" width="50" height="5" />

        {/* Les piliers, evases vers le bas et donc legerement inclines vers
            l'interieur. Un torii aux montants verticaux paraitrait instable. */}
        <path d="M32.5 29.5H38.7L40.3 74H30.9Z" />
        <path d="M61.3 29.5H67.5L69.1 74H59.7Z" />
      </g>

      {/* Le sakura. Le rose le detache du torii sans qu'on ait besoin d'evider
          le portique autour de lui, comme le faisait la version monochrome :
          la couleur fait le travail que le vide faisait. */}
      <g transform="translate(70 29)">
        <g transform="scale(1.5)">
          {PETALES.map((a) => (
            <path key={a} d={PETALE} transform={`rotate(${a})`} fill="var(--lm-petale, #F4A9C4)" />
          ))}

          {/* Ombre au coeur de la corolle. Les cinq petales se recouvrent a
              leur base sur une vraie fleur ; ce disque le suggere sans qu'on
              ait a dessiner cinq recouvrements. */}
          <circle r="3.4" fill="var(--lm-petale-fonce, #E480AC)" opacity="0.55" />

          <g stroke="var(--lm-petale-fonce, #E480AC)" strokeWidth="0.55" strokeLinecap="round">
            {ETAMINES.map((a) => (
              <g key={a} transform={`rotate(${a})`}>
                <line x1="0" y1="0" x2="0" y2="-5.6" />
                <circle cy="-6.1" r="0.85" fill="var(--lm-coeur, #F5C84B)" stroke="none" />
              </g>
            ))}
          </g>

          <circle r="1.5" fill="var(--lm-coeur, #F5C84B)" />
        </g>
      </g>

      {/* Un petale detache, assez grand pour survivre a la reduction. Sa chute
          date la scene au printemps et empeche la fleur d'etre un ornement
          simplement pose la. */}
      <path d={PETALE} transform="translate(79 57) rotate(34)" fill="var(--lm-petale, #F4A9C4)" />
    </svg>
  );
}
