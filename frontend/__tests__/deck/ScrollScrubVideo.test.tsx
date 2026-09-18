import { fireEvent, render } from "@testing-library/react";
import { MotionConfig, motionValue } from "motion/react";
import { describe, expect, it } from "vitest";
import { progressToVideoTime, ScrollScrubVideo } from "@/components/deck/ScrollScrubVideo";

describe("ScrollScrubVideo", () => {
  it("rend une vidéo silencieuse et inline préchargée par métadonnées", () => {
    const { container } = render(
      <MotionConfig reducedMotion="always">
        <ScrollScrubVideo progress={motionValue(0)} />
      </MotionConfig>,
    );
    const video = container.querySelector("video");

    expect(video).toHaveAttribute("src", "/videos/mission-control-scroll-reference.mp4");
    expect(video).toHaveAttribute("poster", "/images/districts/mission-control-city-game-v3.png");
    expect(video).toHaveAttribute("playsinline");
    expect(video).toHaveAttribute("preload", "metadata");
    expect(video).toHaveProperty("muted", true);
    expect(video).not.toHaveAttribute("autoplay");

    Object.defineProperty(video, "duration", { configurable: true, value: 59.8 });
    fireEvent.loadedMetadata(video!);
    expect(video).toHaveProperty("currentTime", 0);
  });

  it("convertit et borne la progression du scroll en temps vidéo", () => {
    expect(progressToVideoTime(0.5, 60)).toBe(30);
    expect(progressToVideoTime(-1, 60)).toBe(0);
    expect(progressToVideoTime(2, 60)).toBe(60);
  });
});
