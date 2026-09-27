/**
 * Réveil de l'API : Render endort l'offre gratuite après quinze minutes sans
 * requête, et le premier visiteur attendait jusqu'à une minute.
 *
 * Cloudflare déclenche ce Worker toutes les cinq minutes (wrangler.toml) : trois
 * occasions de passer avant l'endormissement, une panne passagère ne suffit pas
 * à le laisser partir. Il appelle /healthz, qui répond sans toucher à la base :
 * Neon peut ainsi se suspendre et ne consomme pas son quota.
 *
 * Un appel en échec est retenté trois fois ; le délai laisse le temps d'un
 * redémarrage de l'API. Un échec final lève une erreur, visible dans les
 * journaux du Worker, et la sonde horaire de GitHub (surveillance.yml) alerte
 * par courriel si l'API reste injoignable.
 */

export const ESSAIS = 3;
// Un réveil à froid de Render prend jusqu'à une minute
export const DELAI_MS = 90_000;
export const PAUSE_MS = 10_000;

const attendre = (ms) => new Promise((ok) => setTimeout(ok, ms));

export async function reveiller(url, { appeler = fetch, pause = attendre } = {}) {
  let derniere = "aucun essai";
  for (let essai = 1; essai <= ESSAIS; essai += 1) {
    const debut = Date.now();
    try {
      const reponse = await appeler(url, {
        headers: { "User-Agent": "hanabi-reveil" },
        signal: AbortSignal.timeout(DELAI_MS),
      });
      if (reponse.ok) {
        return { essai, duree_ms: Date.now() - debut, statut: reponse.status };
      }
      derniere = `statut ${reponse.status}`;
    } catch (e) {
      derniere = e?.name === "TimeoutError" ? "délai dépassé" : String(e?.message || e);
    }
    if (essai < ESSAIS) await pause(PAUSE_MS * essai);
  }
  throw new Error(`API injoignable après ${ESSAIS} essais : ${derniere}`);
}

export default {
  async scheduled(_evenement, env, ctx) {
    ctx.waitUntil(
      reveiller(env.API_URL + "/healthz").then((r) =>
        console.log(`API éveillée : essai ${r.essai}, ${r.duree_ms} ms`),
      ),
    );
  },

  // Vérification à la main : ouvrir l'adresse du Worker dans un navigateur
  async fetch(_requete, env) {
    try {
      const r = await reveiller(env.API_URL + "/healthz");
      return Response.json({ api: "éveillée", ...r });
    } catch (e) {
      return Response.json({ api: "injoignable", erreur: e.message }, { status: 502 });
    }
  },
};
