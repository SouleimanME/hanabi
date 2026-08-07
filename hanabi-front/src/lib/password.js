/** Regles de robustesse du mot de passe.
 *
 * Ces regles sont un confort d'interface : elles guident l'utilisateur en
 * direct. La contrainte qui fait foi est celle du serveur
 * (`app/passwords.py`), qui refuse en plus les mots de passe notoirement
 * compromis et ceux qui reprennent le nom ou l'e-mail du titulaire.
 *
 * Les deux jeux de regles doivent rester alignes : une regle plus permissive
 * ici produirait le pire des parcours - une jauge toute verte, puis un refus
 * du serveur sans que l'utilisateur comprenne pourquoi.
 *
 * Les libelles sont des fonctions prenant `t` : les regles sont definies une
 * fois, et traduites au moment de l'affichage.
 */

/** Doit rester egal a MIN_LENGTH dans app/passwords.py. */
export const MIN_PASSWORD_LENGTH = 10;

/** Suites de touches refusees par le serveur. */
const SEQUENCES = /(?:0123|1234|2345|3456|4567|5678|6789|abcd|qwer|azer)/i;

export const PW_RULES = [
  { key: "len", label: (t) => t("pwLen"), test: (v) => v.length >= MIN_PASSWORD_LENGTH },
  { key: "upper", label: (t) => t("pwUpper"), test: (v) => /[A-Z]/.test(v) },
  { key: "lower", label: (t) => t("pwLower"), test: (v) => /[a-z]/.test(v) },
  { key: "symbol", label: (t) => t("pwSymbol"), test: (v) => /[^A-Za-z0-9]/.test(v) },
  {
    key: "varied",
    label: (t) => t("pwVaried"),
    // Reprend les deux refus du serveur qui se verifient sans dictionnaire.
    test: (v) => new Set(v.toLowerCase()).size >= 5 && !SEQUENCES.test(v),
  },
];

/** Nombre de regles satisfaites, de 0 a PW_RULES.length. */
export const pwScore = (value) => PW_RULES.filter((rule) => rule.test(value)).length;

/** Vrai si toutes les regles passent. */
export const isPasswordStrong = (value) => pwScore(value) === PW_RULES.length;
