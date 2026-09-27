/** Visionneuse plein écran : compteur, flèches, fermeture, page figée dessous. */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import Visionneuse from "./Visionneuse.jsx";
import { I18nProvider } from "../../i18n/context.jsx";
import { translator } from "../../i18n/index.js";

const PHOTOS = ["https://images.example/a.jpg", "https://images.example/b.jpg"];

const monter = (props = {}) => {
  const onFermer = vi.fn();
  const rendu = render(
    <I18nProvider t={translator("fr")}>
      <Visionneuse photos={PHOTOS} depart={1} nom="Gourde" onFermer={onFermer} {...props} />
    </I18nProvider>,
  );
  return { onFermer, ...rendu };
};

describe("visionneuse", () => {
  it("s'ouvre sur la photo touchée", () => {
    monter();
    expect(screen.getByRole("dialog", { name: "Gourde" })).toBeInTheDocument();
    expect(screen.getByText("2 / 2")).toBeInTheDocument();
    expect(document.querySelector(".visionneuse img").getAttribute("src")).toBe(PHOTOS[1]);
  });

  it("les flèches passent d'une photo à l'autre", () => {
    monter();
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "ArrowRight" });
    expect(screen.getByText("1 / 2")).toBeInTheDocument();
  });

  it("Fermer et Échap referment", () => {
    const { onFermer } = monter();
    fireEvent.click(screen.getByRole("button", { name: "Fermer" }));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onFermer).toHaveBeenCalledTimes(2);
  });

  it("la page ne défile plus dessous, et retrouve son défilement ensuite", () => {
    const { unmount } = monter();
    expect(document.documentElement.style.overflow).toBe("hidden");
    unmount();
    expect(document.documentElement.style.overflow).toBe("");
  });
});
