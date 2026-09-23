/** Bandeau et préférences : refuser aussi simple qu'accepter, rien de coché d'avance. */
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { BandeauCookies } from "./BandeauCookies.jsx";
import { PreferencesCookies } from "./PreferencesCookies.jsx";
import { I18nProvider } from "../../i18n/context.jsx";
import { translator } from "../../i18n/index.js";

const avec = (element, langue = "fr") =>
  render(<I18nProvider t={translator(langue)}>{element}</I18nProvider>);

describe("bandeau", () => {
  const rappels = () => ({
    onAccepter: vi.fn(),
    onRefuser: vi.fn(),
    onPersonnaliser: vi.fn(),
    onEnSavoirPlus: vi.fn(),
  });

  it("donne au refus le même bouton qu'à l'accord", () => {
    avec(<BandeauCookies {...rappels()} />);
    const refuser = screen.getByRole("button", { name: "Tout refuser" });
    const accepter = screen.getByRole("button", { name: "Tout accepter" });
    expect(refuser.className).toBe(accepter.className);
  });

  it("transmet chaque réponse", () => {
    const r = rappels();
    avec(<BandeauCookies {...r} />);
    fireEvent.click(screen.getByRole("button", { name: "Tout refuser" }));
    fireEvent.click(screen.getByRole("button", { name: "Personnaliser" }));
    expect(r.onRefuser).toHaveBeenCalledOnce();
    expect(r.onPersonnaliser).toHaveBeenCalledOnce();
    expect(r.onAccepter).not.toHaveBeenCalled();
  });

  it("est une région nommée, que le lecteur d'écran annonce", () => {
    avec(<BandeauCookies {...rappels()} />);
    expect(screen.getByRole("region", { name: "Mesure d'audience" })).toBeInTheDocument();
  });

  it("parle la langue de la page", () => {
    avec(<BandeauCookies {...rappels()} />, "en");
    expect(screen.getByRole("button", { name: "Reject all" })).toBeInTheDocument();
  });
});

describe("préférences", () => {
  it("ne coche rien d'avance sans choix antérieur", () => {
    avec(<PreferencesCookies choix={null} onEnregistrer={vi.fn()} onClose={vi.fn()} />);
    expect(screen.getByRole("switch")).not.toBeChecked();
  });

  it("reprend le choix déjà fait", () => {
    avec(
      <PreferencesCookies choix={{ audience: true }} onEnregistrer={vi.fn()} onClose={vi.fn()} />,
    );
    expect(screen.getByRole("switch")).toBeChecked();
  });

  it("enregistre l'interrupteur tel qu'il est", () => {
    const onEnregistrer = vi.fn();
    avec(<PreferencesCookies choix={null} onEnregistrer={onEnregistrer} onClose={vi.fn()} />);
    fireEvent.click(screen.getByRole("switch", { name: "Mesure d'audience rattachée au compte" }));
    fireEvent.click(screen.getByRole("button", { name: "Enregistrer mes choix" }));
    expect(onEnregistrer).toHaveBeenCalledWith({ audience: true });
  });
});
