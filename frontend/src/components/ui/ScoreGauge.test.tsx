import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ScoreGauge } from "./ScoreGauge";

describe("ScoreGauge Component", () => {
  it("renders STRONG BUY badge for high positive score", () => {
    render(
      <ScoreGauge
        score={65.5}
        verdict="STRONG_LONG"
        counts={{ BULL: 6, BEAR: 1, NEUTRAL: 3, NA: 0 }}
      />
    );

    expect(screen.getByText("Skor Konfluensi")).toBeInTheDocument();
    expect(screen.getByText("STRONG BUY")).toBeInTheDocument();
    expect(screen.getByText("+65.5")).toBeInTheDocument();
    expect(screen.getByText("▲ 6")).toBeInTheDocument();
    expect(screen.getByText("▼ 1")).toBeInTheDocument();
  });

  it("renders STRONG SELL badge for negative score", () => {
    render(
      <ScoreGauge
        score={-60.0}
        verdict="STRONG_SHORT"
        counts={{ BULL: 0, BEAR: 8, NEUTRAL: 2, NA: 0 }}
      />
    );

    expect(screen.getByText("STRONG SELL")).toBeInTheDocument();
    expect(screen.getByText("-60.0")).toBeInTheDocument();
  });

  it("renders compact mode correctly", () => {
    render(
      <ScoreGauge
        score={35.0}
        verdict="LONG"
        compact
      />
    );

    expect(screen.getByText("+35")).toBeInTheDocument();
    expect(screen.queryByText("Skor Konfluensi")).not.toBeInTheDocument();
  });
});
