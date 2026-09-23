/** Recherche du nonce anti-robots, hors du fil principal. */

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

self.onmessage = async (event) => {
  const { salt, difficulty, id } = event.data;
  const encodeur = new TextEncoder();

  try {
    let nonce = 0;
    for (;;) {
      const empreinte = new Uint8Array(
        await crypto.subtle.digest("SHA-256", encodeur.encode(`${salt}${nonce}`)),
      );
      if (leadingZeroBits(empreinte) >= difficulty) {
        self.postMessage({ id, nonce: String(nonce) });
        return;
      }
      nonce++;
    }
  } catch (erreur) {
    self.postMessage({ id, erreur: String(erreur) });
  }
};
