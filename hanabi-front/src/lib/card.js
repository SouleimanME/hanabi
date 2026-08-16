/** Detection et validation d'une carte bancaire, cote saisie.
 *
 * Objectif : dire tout de suite ce qui ne va pas, plutot que de laisser partir
 * un paiement voue a l'echec. Rien ici n'est une mesure de securite - le
 * controle qui compte est celui du prestataire de paiement, qui seul connait
 * l'etat reel de la carte.
 *
 * Rappel important : dans une vraie boutique, ces champs n'appartiennent pas au
 * site. On integre l'iframe du prestataire (Stripe Elements et equivalents), qui
 * renvoie un jeton : le numero de carte ne traverse jamais le serveur, ce qui
 * evite d'entrer dans le perimetre PCI-DSS. Le schema `CheckoutIn` du backend
 * prevoit deja ce `payment_token`.
 */

/** Reseaux reconnus, avec leur mise en forme et leurs longueurs valides. */
const BRANDS = [
  {
    id: "amex",
    label: "American Express",
    pattern: /^3[47]/,
    lengths: [15],
    gaps: [4, 10],
    cvcLength: 4,
  },
  {
    id: "visa",
    label: "Visa",
    pattern: /^4/,
    lengths: [13, 16, 19],
    gaps: [4, 8, 12, 16],
    cvcLength: 3,
  },
  {
    id: "mastercard",
    label: "Mastercard",
    // 51-55, ou la plage 2221-2720 ouverte en 2017.
    //
    // La plage est decrite sur QUATRE chiffres, ses deux bornes etant elles-memes
    // a quatre chiffres. Une version anterieure la resumait sur trois - `2[2-9]`
    // acceptait tout 222x - et classait donc 2220 en Mastercard, un prefixe qui
    // n'appartient a personne. Aucune carte reelle ne commence ainsi, mais une
    // regle approchee finit toujours par etre lue comme exacte : autant ecrire
    // la vraie. La contrepartie est que le reseau se revele au quatrieme chiffre
    // au lieu du troisieme, ce qui ne change ni le groupage ni la longueur
    // attendue.
    pattern: /^(5[1-5]|222[1-9]|22[3-9]\d|2[3-6]\d\d|27[01]\d|2720)/,
    lengths: [16],
    gaps: [4, 8, 12],
    cvcLength: 3,
  },
];

const GENERIC = { id: "unknown", label: "", lengths: [16, 19], gaps: [4, 8, 12, 16], cvcLength: 3 };

/** Ne garde que les chiffres. */
export const digitsOnly = (value) => (value || "").replace(/\D/g, "");

/** Identifie le reseau d'apres les premiers chiffres. */
export function detectBrand(value) {
  const digits = digitsOnly(value);
  return BRANDS.find((brand) => brand.pattern.test(digits)) || GENERIC;
}

/**
 * Met le numero en forme au fil de la saisie, selon le reseau detecte.
 * American Express se groupe en 4-6-5, les autres en blocs de quatre.
 */
export function formatCardNumber(value) {
  const brand = detectBrand(value);
  const digits = digitsOnly(value).slice(0, Math.max(...brand.lengths));
  let out = "";
  for (let i = 0; i < digits.length; i++) {
    if (brand.gaps.includes(i)) out += " ";
    out += digits[i];
  }
  return out;
}

/**
 * Algorithme de Luhn : la cle de controle presente sur toute carte.
 *
 * Detecte les fautes de frappe et les chiffres transposes, pas une carte
 * invalide ou sans provision.
 */
export function luhnValid(value) {
  const digits = digitsOnly(value);
  if (digits.length < 12) return false;
  let sum = 0;
  let double = false;
  for (let i = digits.length - 1; i >= 0; i--) {
    let d = Number(digits[i]);
    if (double) {
      d *= 2;
      if (d > 9) d -= 9;
    }
    sum += d;
    double = !double;
  }
  return sum % 10 === 0;
}

/** Numero complet, de longueur plausible et cle de Luhn correcte. */
export function cardNumberValid(value) {
  const brand = detectBrand(value);
  return brand.lengths.includes(digitsOnly(value).length) && luhnValid(value);
}

/** Met l'expiration en forme : « 1226 » devient « 12/26 ». */
export function formatExpiry(value) {
  const digits = digitsOnly(value).slice(0, 4);
  // Un mois saisi de 2 a 9 ne peut etre que 02..09 : on complete le zero.
  if (digits.length === 1 && Number(digits) > 1) return `0${digits}/`;
  if (digits.length <= 2) return digits;
  return `${digits.slice(0, 2)}/${digits.slice(2)}`;
}

/** Expiration complete, mois plausible et date non depassee. */
export function expiryValid(value) {
  const digits = digitsOnly(value);
  if (digits.length !== 4) return false;
  const month = Number(digits.slice(0, 2));
  if (month < 1 || month > 12) return false;

  const year = 2000 + Number(digits.slice(2));
  const now = new Date();
  // Une carte reste valable jusqu'au dernier jour de son mois d'expiration :
  // on compare donc au premier jour du mois suivant.
  return new Date(year, month, 1) > now;
}

/** Longueur du code de securite, 4 chiffres chez American Express. */
export const cvcLength = (cardValue) => detectBrand(cardValue).cvcLength;

export const cvcValid = (cvc, cardValue) => digitsOnly(cvc).length === cvcLength(cardValue);
