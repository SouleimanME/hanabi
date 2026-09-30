/**
 * Réveil d'un serveur Render : l'offre gratuite s'endort après quinze minutes sans
 * requête, et le premier visiteur attendait jusqu'à une minute.
 *
 * Cloudflare déclenche ce Worker toutes les cinq minutes (wrangler.toml) : trois
 * occasions de passer avant l'endormissement, une panne passagère ne suffit pas
 * à le laisser partir. Il appelle API_URL + /healthz, une sonde qui ne touche à
 * rien d'autre. Depuis le 2026-09-30, API_URL désigne le serveur de la boutique ;
 * l'adresse se règle dans le tableau de bord de Cloudflare, pas dans ce dépôt.
 *
 * Un appel en échec est retenté trois fois ; le délai laisse le temps d'un
 * redémarrage. Un échec final lève une erreur, visible dans les journaux du Worker.
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

// Sans adresse réglée, le Worker le dit au lieu d'appeler « undefined/healthz »
export function sonde(env) {
  if (!env.API_URL) throw new Error("API_URL n'est pas réglée dans les variables du Worker");
  return env.API_URL.replace(/\/$/, "") + "/healthz";
}

export default {
  async scheduled(_evenement, env, ctx) {
    ctx.waitUntil(
      reveiller(sonde(env)).then((r) =>
        console.log(`Serveur éveillé : essai ${r.essai}, ${r.duree_ms} ms`),
      ),
    );
  },

  // Vérification à la main : ouvrir l'adresse du Worker dans un navigateur
  async fetch(_requete, env) {
    try {
      const r = await reveiller(sonde(env));
      return Response.json({ api: "éveillée", ...r });
    } catch (e) {
      return Response.json({ api: "injoignable", erreur: e.message }, { status: 502 });
    }
  },
};
