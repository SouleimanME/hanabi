/** Resolution des defis anti-robots, cote navigateur.
 *
 * Le serveur exige, pour chaque formulaire public, une preuve de travail : il
 * faut trouver un `nonce` tel que sha256(sel + nonce) commence par N bits a
 * zero. Le calcul coute quelques centaines de millisecondes.
 *
 * Deux precautions pour que l'utilisateur ne le sente jamais :
 *
 *   1. Le defi est demande et resolu des l'ouverture du formulaire, pendant la
 *      saisie. Au moment de valider, la preuve est deja prete : la latence
 *      percue est nulle.
 *
 *   2. La recherche tourne dans un WEB WORKER, sur un fil separe. Le fil
 *      principal n'en voit rien : ni image perdue, ni frappe en retard.
 *
 * Le point 2 corrigeait auparavant le probleme a l'envers. Le calcul vivait
 * dans la page et rendait la main toutes les deux mille tentatives, mais chaque
 * tentative faisait `await crypto.subtle.digest(...)` : une promesse deja
 * resolue ne cede qu'a la file de MICROTACHES, videe entierement avant que le
 * navigateur ne puisse peindre. Le fil principal restait donc fige par blocs de
 * deux mille hachages - des dizaines de millisecondes chacun, quand une image a
 * soixante par seconde n'en dispose que de seize.
 *
 * Le symptome se voyait partout parce que la preuve est demandee partout :
 * ouverture de l'accueil, ouverture du formulaire de connexion, fiche produit,
 * et une nouvelle preuve relancee en arriere-plan apres chaque usage.
 *
 * Web Crypto (`crypto.subtle.digest`) est natif et disponible dans un worker,
 * donc pas de dependance ni de portage de SHA-256 en JavaScript.
 */

import { request } from "./api.js";

/** Fil de calcul partage, cree au premier besoin.
 *
 * Un seul worker suffit : les preuves sont demandees l'une apres l'autre, et en
 * garder un vivant evite de payer un demarrage a chaque formulaire ouvert.
 */
let worker = null;
let workerIndisponible = false;
let compteur = 0;

function obtenirWorker() {
  if (worker || workerIndisponible) return worker;
  try {
    worker = new Worker(new URL("./antibot.worker.js", import.meta.url), { type: "module" });
  } catch {
    // Navigateur sans worker de module, ou contexte qui l'interdit. On retombe
    // sur le calcul dans la page : moins fluide, mais le formulaire reste
    // utilisable, ce qui prime.
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

/** Recherche du nonce dans la page, uniquement si le worker est indisponible.
 *
 * Conserve la respiration periodique : sans worker, c'est le seul moyen de ne
 * pas figer completement l'onglet. Elle ne suffit pas a garantir la fluidite -
 * c'est precisement pourquoi le worker existe - mais elle evite le pire.
 */
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

/**
 * Cherche un nonce satisfaisant la difficulte demandee.
 *
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

/**
 * Obtient un defi pour un usage donne et le resout.
 *
 * Le bloc renvoye se joint tel quel au corps de la requete, sous la cle
 * `antibot`. `honeypot` part vide : seul un robot le remplit.
 *
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
