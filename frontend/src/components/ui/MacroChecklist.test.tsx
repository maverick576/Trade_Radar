import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MacroChecklist, type MacroCheckItem } from "./MacroChecklist";

describe("MacroChecklist Component", () => {
  const sampleChecks: MacroCheckItem[] = [
    { id: "M1", name: "Tren Besar", passed: true, detail: "H4 dan D1 mendukung" },
    { id: "M2", name: "Berita", passed: false, detail: "USD High-impact dalam 10m" },
    { id: "M3", name: "Volatilitas ATR", passed: true, detail: "Volatilitas normal" },
  ];

  it("renders checklist with passed and blocked checks", () => {
    render(
      <MacroChecklist
        passed={false}
        checks={sampleChecks}
        blockedBy={["M2"]}
      />
    );

    expect(screen.getByText("Macro Filter (M1–M8)")).toBeInTheDocument();
    expect(screen.getByText("⚠ 1 TERBLOKIR")).toBeInTheDocument();
    expect(screen.getByText("Tren Besar")).toBeInTheDocument();
    expect(screen.getByText("USD High-impact dalam 10m")).toBeInTheDocument();
    expect(screen.getByText("Gagal")).toBeInTheDocument();
  });

  it("renders all passed badge when macro filter passes", () => {
    render(
      <MacroChecklist
        passed={true}
        checks={[{ id: "M1", name: "Tren Besar", passed: true, detail: "Lolos" }]}
        blockedBy={[]}
      />
    );

    expect(screen.getByText("✓ SEMUA LOLOS")).toBeInTheDocument();
  });
});
