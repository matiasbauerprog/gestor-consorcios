import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import BannerDemo from "./BannerDemo";

const reiniciarDemo = vi.fn();
vi.mock("../demo/index.js", () => ({ reiniciarDemo: () => reiniciarDemo() }));

beforeEach(() => {
  reiniciarDemo.mockClear();
});

describe("BannerDemo", () => {
  it("no promete un reinicio cada 6 horas, que ya no ocurre", () => {
    render(<BannerDemo />);
    expect(screen.queryByText(/6 horas/i)).toBeNull();
  });

  it("explica que los datos viven en la máquina de quien mira", () => {
    render(<BannerDemo />);
    expect(screen.getByText(/en tu navegador/i)).toBeInTheDocument();
  });

  it("aclara que nada se guarda ni se comparte", () => {
    render(<BannerDemo />);
    expect(screen.getByText(/no se guarda|nada de lo que hagas/i)).toBeInTheDocument();
  });

  it("ofrece reiniciar la demo", async () => {
    const user = userEvent.setup();
    render(<BannerDemo />);
    await user.click(screen.getByRole("button", { name: /reiniciar/i }));
    expect(reiniciarDemo).toHaveBeenCalled();
  });
});
