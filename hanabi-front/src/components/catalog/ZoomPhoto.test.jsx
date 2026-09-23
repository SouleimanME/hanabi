/** Zoom de la fiche : molette, pincement, clavier ; la page défile toujours au plein cadre. */
import { describe, it, expect, beforeEach } from "vitest";
import { render, fireEvent, act } from "@testing-library/react";

import { ZoomPhoto } from "./ZoomPhoto.jsx";

// jsdom ne connaît pas l'identifiant des doigts : un PointerEvent minimal
class PointerEventDeTest extends MouseEvent {
  constructor(type, init = {}) {
    super(type, init);
    this.pointerId = init.pointerId ?? 1;
  }
}
window.PointerEvent = PointerEventDeTest;

// jsdom ne mesure rien : un cadre de 400 px de côté
beforeEach(() => {
  Element.prototype.getBoundingClientRect = () => ({
    left: 0,
    top: 0,
    width: 400,
    height: 400,
    right: 400,
    bottom: 400,
    x: 0,
    y: 0,
  });
});

const trame = () => act(() => new Promise((r) => requestAnimationFrame(() => r())));
const echelle = (c) =>
  Number(c.querySelector(".zoom-plan").style.transform.match(/scale\(([\d.]+)\)/)?.[1] ?? 1);

function monter() {
  const { container } = render(
    <ZoomPhoto libelle="Vue 1 sur 1">
      <img alt="" sizes="96px" src="x.jpg" />
    </ZoomPhoto>,
  );
  return { container, zoom: container.querySelector(".zoom") };
}

describe("molette", () => {
  it("agrandit vers le haut et ne fait pas défiler la page", async () => {
    const { container, zoom } = monter();
    const evt = new WheelEvent("wheel", {
      deltaY: -300,
      clientX: 200,
      clientY: 200,
      cancelable: true,
    });
    zoom.dispatchEvent(evt);
    await trame();
    expect(evt.defaultPrevented).toBe(true);
    expect(echelle(container)).toBeGreaterThan(1);
  });

  it("en butée, au plein cadre comme au maximum, la page ne défile pas", async () => {
    const { container, zoom } = monter();
    const minimum = new WheelEvent("wheel", { deltaY: 300, cancelable: true });
    zoom.dispatchEvent(minimum);
    expect(minimum.defaultPrevented).toBe(true);
    for (let i = 0; i < 10; i++) {
      zoom.dispatchEvent(new WheelEvent("wheel", { deltaY: -500, cancelable: true }));
    }
    const maximum = new WheelEvent("wheel", { deltaY: -500, cancelable: true });
    zoom.dispatchEvent(maximum);
    await trame();
    expect(echelle(container)).toBe(4);
    expect(maximum.defaultPrevented).toBe(true);
  });

  it("demande une photo plus grande dès qu'on agrandit", async () => {
    const { container, zoom } = monter();
    zoom.dispatchEvent(new WheelEvent("wheel", { deltaY: -300, cancelable: true }));
    await trame();
    expect(container.querySelector("img").sizes).toBe("1600px");
  });
});

describe("pincement", () => {
  it("écarter deux doigts agrandit", async () => {
    const { container, zoom } = monter();
    fireEvent.pointerDown(zoom, { pointerId: 1, clientX: 150, clientY: 200 });
    fireEvent.pointerDown(zoom, { pointerId: 2, clientX: 250, clientY: 200 });
    fireEvent.pointerMove(zoom, { pointerId: 1, clientX: 100, clientY: 200 });
    fireEvent.pointerMove(zoom, { pointerId: 2, clientX: 300, clientY: 200 });
    await trame();
    expect(echelle(container)).toBeCloseTo(2, 1);
  });
});

describe("clic", () => {
  it("un clic agrandit, un second revient au plein cadre", async () => {
    const { container, zoom } = monter();
    fireEvent.pointerDown(zoom, { pointerId: 1, button: 0, clientX: 100, clientY: 100 });
    fireEvent.pointerUp(zoom, { pointerId: 1, button: 0, clientX: 100, clientY: 100 });
    await trame();
    expect(echelle(container)).toBe(2.5);
    expect(zoom).toHaveAttribute("aria-pressed", "true");
    fireEvent.pointerDown(zoom, { pointerId: 1, button: 0, clientX: 100, clientY: 100 });
    fireEvent.pointerUp(zoom, { pointerId: 1, button: 0, clientX: 100, clientY: 100 });
    await trame();
    expect(echelle(container)).toBe(1);
  });

  it("un glisser n'est pas un clic", async () => {
    const { container, zoom } = monter();
    fireEvent.pointerDown(zoom, { pointerId: 1, button: 0, clientX: 100, clientY: 100 });
    fireEvent.pointerMove(zoom, { pointerId: 1, clientX: 160, clientY: 100 });
    fireEvent.pointerUp(zoom, { pointerId: 1, button: 0, clientX: 160, clientY: 100 });
    await trame();
    expect(echelle(container)).toBe(1);
  });

  it("Entrée fait comme le clic, au centre", async () => {
    const { container, zoom } = monter();
    expect(zoom).toHaveAttribute("role", "button");
    fireEvent.keyDown(zoom, { key: "Enter" });
    await trame();
    expect(echelle(container)).toBe(2.5);
  });
});

describe("clavier", () => {
  it("+ agrandit, 0 revient au plein cadre, sans dépasser quatre fois", async () => {
    const { container, zoom } = monter();
    for (let i = 0; i < 6; i++) fireEvent.keyDown(zoom, { key: "+" });
    await trame();
    expect(echelle(container)).toBe(4);
    fireEvent.keyDown(zoom, { key: "0" });
    await trame();
    expect(echelle(container)).toBe(1);
    expect(zoom.dataset.zoom).toBe("non");
  });

  it("au plein cadre, les flèches gardent leur rôle", () => {
    const { zoom } = monter();
    const evt = new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true, cancelable: true });
    zoom.dispatchEvent(evt);
    expect(evt.defaultPrevented).toBe(false);
  });
});
