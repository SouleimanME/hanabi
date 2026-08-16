/** Internationalisation.
 *
 * Le vrai risque n'est pas qu'une traduction soit mauvaise - une relecture
 * humaine s'en charge - mais qu'elle MANQUE. Un dictionnaire secondaire
 * derive silencieusement : on ajoute une cle en francais, l'interface reste
 * correcte pour le developpeur qui travaille en francais, et la version
 * espagnole affiche un identifiant technique a la place d'une phrase.
 *
 * Le module avertit en console au chargement, en developpement. C'est utile,
 * mais un avertissement ne casse aucune construction : il se lit s'il est lu.
 * Ici, il bloque.
 */
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
    const marqueurs = (texte) =>
      typeof texte === "string" ? [...texte.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort() : [];

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
    for (const [code, dict] of Object.entries(DICTIONNAIRES)) {
      const vides = Object.entries(dict)
        .filter(([, v]) => typeof v === "string" && v.trim() === "")
        .map(([k]) => k);
      expect(vides, `valeur(s) vide(s) en ${code}`).toEqual([]);
    }
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
  /* CE QUE CE TEST EMPECHE.
   *
   * Une cle supprimee du code mais laissee dans les trois dictionnaires ne
   * casse rien : elle se traduit, elle se relit, elle survit aux relectures. Et
   * elle MENT - `infoNote` annoncait « la modification en ligne n'est pas encore
   * disponible » plusieurs semaines apres que l'ecran d'edition existait. Le
   * jour ou quelqu'un la reutilise, il affiche une phrase fausse.
   *
   * Trois cles mortes ont ete trouvees a l'ecriture de ce test : `infoNote`,
   * `ship48` et `sort`.
   */

  // Cles CONSTRUITES a l'execution : `t("cat_" + categorie)`. Aucune analyse
  // statique ne peut les voir, et les compter comme mortes rendrait ce test
  // faux plutot qu'utile. La liste est courte et se relit.
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
