// node --test hanabi-reveil
import { test } from "node:test";
import assert from "node:assert/strict";

import worker, { ESSAIS, reveiller, sonde } from "./worker.js";

const repond = (status) => async () => ({ ok: status < 400, status });
const sansPause = async () => {};

test("une API éveillée répond au premier essai", async () => {
  const r = await reveiller("https://api.test/healthz", { appeler: repond(200), pause: sansPause });
  assert.equal(r.essai, 1);
  assert.equal(r.statut, 200);
});

test("une API qui redémarre est retentée, avec une pause qui s'allonge", async () => {
  const reponses = [new Error("réseau"), { ok: false, status: 502 }, { ok: true, status: 200 }];
  const pauses = [];
  const r = await reveiller("https://api.test/healthz", {
    appeler: async () => {
      const suivante = reponses.shift();
      if (suivante instanceof Error) throw suivante;
      return suivante;
    },
    pause: async (ms) => pauses.push(ms),
  });
  assert.equal(r.essai, 3);
  assert.deepEqual(pauses, [10_000, 20_000]);
});

test("après tous les essais, l'échec se voit dans les journaux", async () => {
  let appels = 0;
  await assert.rejects(
    reveiller("https://api.test/healthz", {
      appeler: async () => {
        appels += 1;
        return { ok: false, status: 503 };
      },
      pause: sansPause,
    }),
    /injoignable après 3 essais : statut 503/,
  );
  assert.equal(appels, ESSAIS);
});

test("le déclenchement vise la sonde de vie, jamais celle qui touche la base", async () => {
  const vus = [];
  const fetchOrigine = globalThis.fetch;
  globalThis.fetch = async (url) => {
    vus.push(url);
    return { ok: true, status: 200 };
  };
  try {
    const attentes = [];
    await worker.scheduled({}, { API_URL: "https://api.test" }, { waitUntil: (p) => attentes.push(p) });
    await Promise.all(attentes);
  } finally {
    globalThis.fetch = fetchOrigine;
  }
  assert.deepEqual(vus, ["https://api.test/healthz"]);
});

test("le calendrier déclenche toutes les cinq minutes", async () => {
  const { readFile } = await import("node:fs/promises");
  const config = await readFile(new URL("./wrangler.toml", import.meta.url), "utf8");
  assert.match(config, /crons = \["\*\/5 \* \* \* \*"\]/);
});

test("l'adresse vient du tableau de bord : le dépôt public ne l'écrit pas, un déploiement la garde", async () => {
  const { readFile } = await import("node:fs/promises");
  const config = await readFile(new URL("./wrangler.toml", import.meta.url), "utf8");
  assert.doesNotMatch(config, /^\s*API_URL\s*=/m);
  assert.match(config, /^keep_vars = true$/m);
});

test("sans adresse réglée, le Worker le dit clairement", () => {
  assert.throws(() => sonde({}), /API_URL n'est pas réglée/);
  assert.equal(sonde({ API_URL: "https://serveur.test/" }), "https://serveur.test/healthz");
});
