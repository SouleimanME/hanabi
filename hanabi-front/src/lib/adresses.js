/** Adresses françaises : Base Adresse Nationale, servie par la Géoplateforme de
 *  l'IGN. Gratuite, sans clé, 50 requêtes par seconde et par adresse IP. Une
 *  panne ne bloque rien : sans réponse, le champ reste un champ ordinaire. */

const API = "https://data.geopf.fr/geocodage/search";

// Sur une enveloppe, « Lyon 3e Arrondissement » s'écrit « Lyon »
const nomDeVille = (ville = "") => ville.replace(/\s+\d+(er|e)\s+Arrondissement$/i, "");

async function chercher(parametres, signal) {
  const reponse = await fetch(`${API}?${new URLSearchParams(parametres)}`, { signal });
  if (!reponse.ok) return [];
  const { features = [] } = await reponse.json();
  return features.map((f) => f.properties);
}

/** Adresses complètes qui commencent comme la saisie, cinq au plus. */
export async function suggererAdresses(saisie, signal) {
  const q = saisie.trim();
  if (q.length < 3) return [];
  const trouvees = await chercher({ q, index: "address", autocomplete: "1", limit: "5" }, signal);
  return (
    trouvees
      // Une commune seule n'est pas une adresse de livraison
      .filter((p) => p.type !== "municipality" && p.postcode && p.city)
      .map((p) => ({ id: p.id, adresse: p.name, cp: p.postcode, ville: nomDeVille(p.city) }))
  );
}

/** Communes d'un code postal : 01100 en compte sept, 75011 une seule. */
export async function villesDuCodePostal(cp, signal) {
  if (!/^\d{5}$/.test(cp)) return [];
  const trouvees = await chercher(
    { q: cp, index: "address", type: "municipality", limit: "10" },
    signal,
  );
  // La recherche est approchée : elle rend aussi des communes voisines
  const villes = trouvees.filter((p) => p.postcode === cp).map((p) => nomDeVille(p.city));
  return [...new Set(villes)];
}
