/** Code promo : les codes du moment s'appliquent d'un clic. */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import { PromoField } from "./PromoField.jsx";
import { I18nProvider } from "../../i18n/context.jsx";
import { translator } from "../../i18n/index.js";

const monter = (onApply) =>
  render(
    <I18nProvider t={translator("fr")}>
      <PromoField onApply={onApply} onClear={vi.fn()} />
    </I18nProvider>,
  );

describe("codes du moment", () => {
  it("un clic applique le code, sans le taper", async () => {
    const onApply = vi.fn().mockResolvedValue(null);
    monter(onApply);
    fireEvent.click(screen.getByRole("button", { name: /DROP5/ }));
    await waitFor(() => expect(onApply).toHaveBeenCalledWith("DROP5"));
  });

  it("chaque code dit ce qu'il offre", () => {
    monter(vi.fn());
    const groupe = screen.getByRole("group", { name: "Codes du moment" });
    expect(groupe).toHaveTextContent("BIENVENUE10−10 %");
    expect(groupe).toHaveTextContent("DROP5−5 € dès 30 €");
    expect(groupe).toHaveTextContent("PORTOFFERTport offert");
  });

  it("un refus du serveur s'affiche sous le champ", async () => {
    monter(vi.fn().mockResolvedValue("Code inconnu."));
    fireEvent.click(screen.getByRole("button", { name: /PORTOFFERT/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Code inconnu.");
  });
});
