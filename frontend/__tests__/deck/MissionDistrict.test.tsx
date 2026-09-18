import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MotionConfig, motionValue } from "motion/react";
import { buildCinematicCameraKeyframes, MissionDistrict } from "@/components/deck/MissionDistrict";
import { MODULES } from "@/lib/modules";

describe("MissionDistrict", () => {
  it("fait passer la caméra par un pic de zoom et une occultation entre deux scènes", () => {
    const keyframes = buildCinematicCameraKeyframes([
      { x: 0, y: 0, scale: 1 },
      { x: 240, y: -180, scale: 1.5 },
    ]);

    expect(Math.max(...keyframes.scale)).toBeGreaterThan(2);
    expect(Math.max(...keyframes.gate)).toBeGreaterThan(0.9);
    expect(Math.max(...keyframes.blur)).toBe(8);
    expect(keyframes.x.at(-1)).toBe(240);
    expect(keyframes.y.at(-1)).toBe(-180);
    expect(keyframes.gate.at(-1)).toBe(0);
  });

  it("rend un bâtiment navigable pour chaque module", () => {
    render(
      <MotionConfig reducedMotion="always">
        <MissionDistrict progress={motionValue(0)} active={0} selectedModule={0} />
      </MotionConfig>,
    );

    expect(
      screen.getByRole("img", {
        name: "Carte illustrée des quartiers et modules de Mission Control",
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByRole("link")).toHaveLength(MODULES.length);
    expect(screen.getByRole("link", { name: /Budget/ })).toHaveAttribute("href", "/budget");
    expect(screen.getByRole("link", { name: /Voyage/ })).toHaveAttribute("href", "/voyage");
    expect(document.querySelector(".district-city-art")).toHaveAttribute(
      "href",
      "/images/districts/mission-control-city-game-v3.png",
    );
    expect(document.querySelectorAll(".district-life")).toHaveLength(MODULES.length);
    expect(document.querySelectorAll(".district-resident")).toHaveLength(0);
  });
});
