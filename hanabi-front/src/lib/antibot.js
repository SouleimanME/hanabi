/** Resolution des defis anti-robots, cote navigateur. */

import { request } from "./api.js";

/** Fil de calcul partage, cree au premier besoin. */
let worker = null;
let workerIndisponible = false;
let compteur = 0;

function obtenirWorker() {
  if (worker || workerIndisponible) return worker;
  try {
    worker = new Worker(new URL("./antibot.worker.js", import.meta.url), { type: "module" });
  } catch {
    // Navigateur sans worker de module, ou contexte qui l'interdit
    workerIndisponible = true;
  }
  return worker;
}

/** Compte les bits a zero en tete d'une empreinte. */
function leadingZeroBits(bytes) {
  let bits = 0;
  for (const byte of bytes) {
    if (byte === 0) {
      bits += 8;
      continue;
    }
    // 8 moins la position du bit de poids fort a 1.
    bits += 8 - byte.toString(2).length;
    break;
  }
  return bits;
}

/** Recherche du nonce dans la page, uniquement si le worker est indisponible. */
const CHUNK = 500;
const breathe = () => new Promise((resolve) => setTimeout(resolve, 0));

async function minerDansLaPage(salt, difficulty, signal) {
  const encodeur = new TextEncoder();
  let nonce = 0;
  for (;;) {
    for (let i = 0; i < CHUNK; i++) {
      const empreinte = new Uint8Array(
        await crypto.subtle.digest("SHA-256", encodeur.encode(`${salt}${nonce}`)),
      );
      if (leadingZeroBits(empreinte) >= difficulty) return String(nonce);
      nonce++;
    }
    if (signal?.aborted) throw new DOMException("Resolution annulee", "AbortError");
    await breathe();
  }
}

/** Cherche un nonce satisfaisant la difficulte demandee.
 * @param {string} salt
 * @param {number} difficulty bits a zero exiges
 * @param {{signal?: AbortSignal}} [opts]
 * @returns {Promise<string>}
 */
function mine(salt, difficulty, { signal } = {}) {
  const fil = obtenirWorker();
  if (!fil) return minerDansLaPage(salt, difficulty, signal);

  return new Promise((resolve, reject) => {
    const id = ++compteur;

    const surReponse = (event) => {
      // Le worker est partage : on ignore ce qui ne repond pas a notre demande.
      if (event.data.id !== id) return;
      nettoyer();
      if (event.data.erreur) reject(new Error(event.data.erreur));
      else resolve(event.data.nonce);
    };

    // Un worker qui echoue a se charger ne repondra jamais : on bascule sur le
    // calcul dans la page plutot que de laisser la promesse en suspens.
    const surErreur = () => {
      nettoyer();
      workerIndisponible = true;
      worker = null;
      minerDansLaPage(salt, difficulty, signal).then(resolve, reject);
    };

    const surAbandon = () => {
      nettoyer();
      // Le worker continue de chercher dans le vide ; on le remplace pour ne
      // pas laisser un fil occupe a un calcul dont plus personne ne veut.
      fil.terminate();
      worker = null;
      reject(new DOMException("Resolution annulee", "AbortError"));
    };

    function nettoyer() {
      fil.removeEventListener("message", surReponse);
      fil.removeEventListener("error", surErreur);
      signal?.removeEventListener("abort", surAbandon);
    }

    fil.addEventListener("message", surReponse);
    fil.addEventListener("error", surErreur);
    signal?.addEventListener("abort", surAbandon);
    fil.postMessage({ salt, difficulty, id });
  });
}

/** Obtient un defi pour un usage donne et le resout.
 * @param {"register"|"login"|"notify"|"review"} purpose
 * @param {{signal?: AbortSignal}} [opts]
 * @returns {Promise<object>}
 */
export async function solveChallenge(purpose, opts = {}) {
  const challenge = await request(`/security/challenge?purpose=${encodeURIComponent(purpose)}`);
  const nonce = await mine(challenge.salt, challenge.difficulty, opts);
  return {
    fields: {
      salt: challenge.salt,
      issued_at: challenge.issued_at,
      signature: challenge.signature,
      nonce,
      honeypot: "",
    },
    // Politique transmise par le serveur, pour ne pas la dupliquer ici.
    solvedAt: Date.now(),
    minSeconds: challenge.min_seconds,
    ttlSeconds: challenge.ttl_seconds,
  };
}
