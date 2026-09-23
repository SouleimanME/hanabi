/** Tailles d'image proposées au navigateur. */
import { describe, it, expect } from "vitest";

import { LARGEURS, sourcesAdaptees } from "./images.js";

const PHOTO =
  "https://images.unsplash.com/photo-1?w=1200&h=1200&q=80&auto=format&fit=crop&crop=focalpoint&fp-x=0.5";

describe("srcset", () => {
  it("propose chaque largeur, du plus petit au plus grand", () => {
    const valeurs = sourcesAdaptees(PHOTO).split(", ");
    expect(valeurs.map((v) => Number(v.split(" ")[1].replace("w", "")))).toEqual(LARGEURS);
  });

  it("garde le carré et le recadrage choisi", () => {
    const premiere = sourcesAdaptees(PHOTO).split(", ")[0].split(" ")[0];
    const u = new URL(premiere);
    expect([u.searchParams.get("w"), u.searchParams.get("h")]).toEqual(["160", "160"]);
    expect(u.searchParams.get("fp-x")).toBe("0.5");
  });

  it("garde les proportions d'une photo qui n'est pas carrée", () => {
    const u = new URL(
      sourcesAdaptees(PHOTO.replace("h=1200", "h=800")).split(", ")[1].split(" ")[0],
    );
    expect([u.searchParams.get("w"), u.searchParams.get("h")]).toEqual(["320", "213"]);
  });

  it("laisse tranquille une photo d'une autre source", () => {
    expect(sourcesAdaptees("https://exemple.fr/photo.jpg")).toBeNull();
    expect(sourcesAdaptees("data:image/png;base64,AAAA")).toBeNull();
    expect(sourcesAdaptees("torii,#E0452A,#0A0605")).toBeNull();
  });
});
