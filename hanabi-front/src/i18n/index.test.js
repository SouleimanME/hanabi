/** Internationalisation. */
import { describe, it, expect } from "vitest";

import { translator, LANGS } from "./index.js";
import fr from "./dictionaries/fr.js";
import en from "./dictionaries/en.js";
import es from "./dictionaries/es.js";

const DICTIONNAIRES = { fr, en, es };

describe("parite des dictionnaires", () => {
  it("declare une entree LANGS pour chaque dictionnaire, et l'inverse", () => {
    expect(LANGS.map((l) => l.code).sort()).toEqual(Object.keys(DICTIONNAIRES).sort());
  });

  it("donne a chaque langue un libelle non vide", () => {
    for (const { code, label } of LANGS) {
      expect(label, `libelle manquant pour ${code}`).toBeTruthy();
    }
  });

  it.each(["en", "es"])("le dictionnaire %s couvre toutes les cles du francais", (code) => {
    const manquantes = Object.keys(fr).filter((cle) => !(cle in DICTIONNAIRES[code]));
    expect(manquantes, `${manquantes.length} cle(s) a traduire en "${code}"`).toEqual([]);
  });

  it.each(["en", "es"])("le dictionnaire %s n'a pas de cle orpheline", (code) => {
    // Une cle qui n'existe plus en francais est du code mort : elle survit aux
    // suppressions et donne l'illusion d'une couverture.
    const orphelines = Object.keys(DICTIONNAIRES[code]).filter((cle) => !(cle in fr));
    expect(orphelines, `cle(s) sans equivalent francais dans "${code}"`).toEqual([]);
  });

  it("emploie les memes marqueurs de substitution dans toutes les langues", () => {
    // Une phrase francaise « Plus que {montant} » traduite sans son {montant}
    // afficherait une phrase amputee, sans que rien ne signale l'erreur.
    const marqueurs = (texte) => {
      if (texte && typeof texte === "object") return marqueurs(texte.other);
      return typeof texte === "string"
        ? [...new Set([...texte.matchAll(/\{(\w+)\}/g)].map((m) => m[1]))].sort()
        : [];
    };

    for (const [code, dict] of Object.entries(DICTIONNAIRES)) {
      if (code === "fr") continue;
      for (const cle of Object.keys(fr)) {
        expect(marqueurs(dict[cle]), `marqueurs divergents pour "${cle}" en ${code}`).toEqual(
          marqueurs(fr[cle]),
        );
      }
    }
  });

  it("ne laisse aucune valeur vide", () => {
    const vide = (v) =>
      typeof v === "string" ? v.trim() === "" : !v?.one?.trim() || !v?.other?.trim();
    for (const [code, dict] of Object.entries(DICTIONNAIRES)) {
      const vides = Object.entries(dict)
        .filter(([, v]) => vide(v))
        .map(([k]) => k);
      expect(vides, `valeur(s) vide(s) en ${code}`).toEqual([]);
    }
  });
});

describe("pluriels", () => {
  it("accorde selon la langue : 0 et 1 au singulier en francais, 1 seul en anglais", () => {
    expect(translator("fr")("objectsN", { n: 1 })).toBe("1 objet");
    expect(translator("fr")("objectsN", { n: 0 })).toBe("0 objet");
    expect(translator("fr")("objectsN", { n: 12 })).toBe("12 objets");
    expect(translator("en")("objectsN", { n: 1 })).toBe("1 object");
    expect(translator("en")("objectsN", { n: 0 })).toBe("0 objects");
  });
});

describe("translator", () => {
  const premiereCle = Object.keys(fr)[0];

  it("rend la traduction de la langue demandee", () => {
    expect(translator("fr")(premiereCle)).toBe(fr[premiereCle]);
    expect(translator("en")(premiereCle)).toBe(en[premiereCle]);
  });

  it("retombe sur le francais pour une langue inconnue", () => {
    expect(translator("de")(premiereCle)).toBe(fr[premiereCle]);
  });

  it("rend la cle elle-meme si elle n'existe nulle part", () => {
    // L'interface reste lisible, et la cle affichee designe exactement ce qu'il
    // faut aller corriger.
    expect(translator("fr")("cle.absente.partout")).toBe("cle.absente.partout");
  });

  it("substitue les variables", () => {
    const t = translator("fr");
    expect(t("cle.absente.{nom}", { nom: "Hanabi" })).toBe("cle.absente.Hanabi");
  });

  it("remplace TOUTES les occurrences d'une meme variable", () => {
    expect(translator("fr")("{x} et {x}", { x: 7 })).toBe("7 et 7");
  });

  it("laisse intact un marqueur dont la variable n'est pas fournie", () => {
    expect(translator("fr")("{a}-{b}", { a: 1 })).toBe("1-{b}");
  });
});

describe("cles orphelines", () => {
  /* Une cle traduite mais jamais affichee est du code mort qu'on continue de traduire. */

  // Cles construites a l'execution : `t("cat_" + categorie)`
  const PREFIXES_DYNAMIQUES = ["cat_", "matiere_", "legal_", "civ", "delivery", "pw"];

  const sources = import.meta.glob("../**/*.{js,jsx}", {
    eager: true,
    query: "?raw",
    import: "default",
  });

  const codeApplicatif = Object.entries(sources)
    .filter(([chemin]) => !chemin.includes(".test.") && !chemin.includes("/dictionaries/"))
    .map(([, contenu]) => contenu)
    .join("\n");

  it("chaque cle du dictionnaire est employee quelque part", () => {
    const employees = new Set([
      ...[...codeApplicatif.matchAll(/\bt\(\s*"([\w.]+)"/g)].map((m) => m[1]),
      ...[...codeApplicatif.matchAll(/key:\s*"(\w+)"/g)].map((m) => m[1]),
    ]);

    const orphelines = Object.keys(fr).filter(
      (cle) =>
        !employees.has(cle) && !PREFIXES_DYNAMIQUES.some((prefixe) => cle.startsWith(prefixe)),
    );

    expect(orphelines, `cle(s) traduite(s) mais jamais affichee(s)`).toEqual([]);
  });
});
