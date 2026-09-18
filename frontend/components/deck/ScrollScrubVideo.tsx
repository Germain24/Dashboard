"use client";

import { useEffect, useRef } from "react";
import { useMotionValueEvent, useReducedMotion, type MotionValue } from "motion/react";

const VIDEO_SRC = "/videos/mission-control-scroll-reference.mp4";
const POSTER_SRC = "/images/districts/mission-control-city-game-v3.png";

export function progressToVideoTime(progress: number, duration: number) {
  return Math.max(0, Math.min(1, progress)) * Math.max(0, duration);
}

/**
 * Vidéo de scrollytelling : la progression du conteneur ne lance pas une
 * lecture classique. Elle déplace la tête de lecture, avec une interpolation
 * requestAnimationFrame pour éviter les saccades provoquées par une succession
 * directe de seeks dans l'événement scroll.
 */
export function ScrollScrubVideo({ progress }: { progress: MotionValue<number> }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const durationRef = useRef(0);
  const targetTimeRef = useRef(0);
  const frameRef = useRef<number | null>(null);
  const reducedMotion = useReducedMotion();

  function renderFrame() {
    const video = videoRef.current;
    if (!video || reducedMotion || durationRef.current === 0) {
      frameRef.current = null;
      return;
    }

    // Une seule écriture par frame : les nombreux événements de scroll sont
    // regroupés, sans lancer plusieurs seeks concurrents dans le décodeur.
    if (Math.abs(targetTimeRef.current - video.currentTime) >= 0.012) {
      video.currentTime = targetTimeRef.current;
    }
    frameRef.current = null;
  }

  function requestFrame() {
    if (frameRef.current === null) {
      frameRef.current = requestAnimationFrame(renderFrame);
    }
  }

  useMotionValueEvent(progress, "change", (latest) => {
    const video = videoRef.current;
    if (!video) return;
    video.dataset.scrollProgress = latest.toFixed(4);
    const duration = durationRef.current || (Number.isFinite(video.duration) ? video.duration : 0);
    if (reducedMotion || duration === 0) return;
    durationRef.current = duration;
    targetTimeRef.current = progressToVideoTime(latest, duration);
    requestFrame();
  });

  useEffect(
    () => () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
    },
    [],
  );

  const handleMetadata = () => {
    const video = videoRef.current;
    if (!video || !Number.isFinite(video.duration)) return;
    durationRef.current = video.duration;
    video.dataset.videoDuration = video.duration.toFixed(4);
    targetTimeRef.current = reducedMotion ? 0 : progressToVideoTime(progress.get(), video.duration);
    video.currentTime = targetTimeRef.current;
  };

  return (
    <div className="scroll-video-stage" aria-hidden="true">
      <video
        ref={videoRef}
        className="scroll-video-media"
        src={VIDEO_SRC}
        poster={POSTER_SRC}
        muted
        playsInline
        preload="metadata"
        tabIndex={-1}
        onLoadedMetadata={handleMetadata}
      />
      <div className="scroll-video-grade" />
      <div className="scroll-video-vignette" />
    </div>
  );
}
