"use client";

import { useEffect, useRef } from "react";

type Particle = {
  x: number;
  y: number;
  // Reaction velocity carries the (very subtle) magnetic nudge toward the
  // cursor. It springs back toward zero and is damped, so the pull is gentle
  // and particles smoothly return to ambient drift when the cursor leaves.
  vx: number;
  vy: number;
  // Each particle has its own gentle ambient flow direction + speed
  baseAngle: number;
  baseSpeed: number;
  size: number;
  baseAlpha: number;
  twinkle: number;
  twinkleSpeed: number;
  // "Energy" = how awake the particle is (0 idle → 1 fully energised).
  // The cursor raises this when nearby. Energy eases up on approach and
  // decays back down when the cursor leaves. Drives brightness, glow size,
  // and a touch more ambient motion activity.
  energy: number;
};

/**
 * ParticleField
 *
 * A subtle, physics-inspired LIVING particle field with an extremely subtle
 * magnetic influence.
 *
 * Design goals (per spec):
 * - Particles are ALWAYS in a constant floating / drifting state. When the
 *   cursor is away they stay soft, subtle, slightly transparent, gently
 *   floating in the background.
 * - The cursor primarily influences visual ENERGY: as it approaches, particles
 *   smoothly become brighter, more visible, and slightly more active — as if
 *   waking up. When the cursor moves away, they settle back to their soft idle
 *   state (glow gradually fades, motion calms).
 * - On top of the energy effect, there is a VERY subtle magnetic nudge: nearby
 *   particles drift gently toward the cursor. The pull is intentionally tiny
 *   (a fraction of a pixel per frame, quadratic falloff, spring-damped) so it
 *   reads as a soft physical attraction — never a strong pull, never snapping
 *   or cutting. Particles smoothly return to ambient drift when the cursor
 *   leaves.
 * - Energy drives brightness/alpha, glow size, and a touch more ambient drift
 *   speed + wobble.
 * - Transitions between idle and awake are smooth, eased, and natural.
 * - No repulsion, no sharp movement, no cutting or snapping.
 *
 * Rendered on a canvas with a pre-rendered glow sprite for performance.
 * Respects prefers-reduced-motion.
 */
export function ParticleField({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mouseRef = useRef({
    x: -9999,
    y: -9999,
    active: false,
    tx: -9999,
    ty: -9999,
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let width = 0;
    let height = 0;
    let dpr = 1;
    let particles: Particle[] = [];
    let rafId = 0;
    let running = true;

    // Pre-rendered glow sprite: solid brand-blue core with a soft halo.
    // Normal source-over blending so it stays visible on a white background.
    const sprite = document.createElement("canvas");
    const SPRITE_SIZE = 48;
    sprite.width = SPRITE_SIZE;
    sprite.height = SPRITE_SIZE;
    const sctx = sprite.getContext("2d");
    if (sctx) {
      const half = SPRITE_SIZE / 2;
      const grad = sctx.createRadialGradient(half, half, 0, half, half, half);
      // Slightly denser sprite so particles read as more solid/visible.
      grad.addColorStop(0, "rgba(73, 123, 249, 1)");
      grad.addColorStop(0.18, "rgba(73, 123, 249, 0.85)");
      grad.addColorStop(0.5, "rgba(73, 123, 249, 0.28)");
      grad.addColorStop(1, "rgba(73, 123, 249, 0)");
      sctx.fillStyle = grad;
      sctx.fillRect(0, 0, SPRITE_SIZE, SPRITE_SIZE);
    }

    const setup = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      const rect = canvas.getBoundingClientRect();
      width = Math.max(1, rect.width);
      height = Math.max(1, rect.height);
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

      // Dense, numerous on larger screens, capped for perf.
      const area = width * height;
      const count = Math.min(320, Math.max(80, Math.floor(area / 4600)));
      particles = new Array(count);
      for (let i = 0; i < count; i++) {
        const angle = Math.random() * Math.PI * 2;
        particles[i] = {
          x: Math.random() * width,
          y: Math.random() * height,
          vx: 0,
          vy: 0,
          // Each particle owns a slow ambient flow vector. This is the
          // "living field" baseline — particles always drift, even with no
          // cursor anywhere on screen.
          baseAngle: angle,
          baseSpeed: 0.05 + Math.random() * 0.12, // very slow drift
          size: Math.random() * 1.6 + 0.8,
          // Idle base alpha is noticeably higher now so particles read as
          // clearly visible/darker when idle (not faded). The cursor's energy
          // lifts them further on hover.
          baseAlpha: Math.random() * 0.2 + 0.45,
          twinkle: Math.random() * Math.PI * 2,
          twinkleSpeed: Math.random() * 0.02 + 0.008,
          energy: 0,
        };
      }
    };

    // ---- Tuning constants -------------------------------------------------
    // Two cursor influences, both very gentle:
    //  1) ENERGY — visual: brightness/visibility + a touch more motion
    //     activity. Always eased; never directional.
    //  2) MAGNETIC — an extremely subtle nudge toward the cursor. Tiny force,
    //     quadratic falloff, spring-damped so it reads as a soft physical
    //     attraction, not a strong pull.
    const INFLUENCE = 230;        // radius of the energy + magnetic field
    const PULL = 0.0036;          // magnetic strength — doubled from 0.0018 (still subtle)
    const VEL_SPRING = 0.02;      // reaction velocity eases back toward zero
    const VEL_DAMPING = 0.96;     // high damping → smooth, fluid easing
    const AMBIENT_WOBBLE = 0.0014;// tiny organic wobble on each flow vector
    const ENERGY_RISE = 0.045;    // how fast energy ramps up near the cursor
    const ENERGY_DECAY = 0.016;   // slower decay → graceful "settling back to sleep"
    const CONNECT_DIST = 132;     // distance for connection lines
    // Idle vs. awake motion range. Energy smoothly scales drift speed and
    // wobble so awake particles feel a little more "active".
    const IDLE_DRIFT_MUL = 1.0;
    const AWAKE_DRIFT_MUL = 1.9;  // up to ~1.9x drift speed when fully awake
    const AWAKE_WOBBLE_MUL = 2.4; // up to ~2.4x wobble when fully awake
    // -----------------------------------------------------------------------

    const draw = () => {
      if (!running) return;
      ctx.clearRect(0, 0, width, height);

      const mouse = mouseRef.current;
      // Ease the effective cursor position so the energy field's center is
      // smooth, never twitchy.
      mouse.x += (mouse.tx - mouse.x) * 0.1;
      mouse.y += (mouse.ty - mouse.y) * 0.1;

      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];

        // 1) Cursor influence: ENERGY (visual) + a very subtle MAGNETIC nudge.
        //    Both keyed off the same cursor distance. The magnetic pull is a
        //    whisper — a fraction of a pixel per frame, quadratic falloff — so
        //    it reads as soft physical attraction, never a strong pull.
        if (mouse.active) {
          const dx = mouse.x - p.x;
          const dy = mouse.y - p.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < INFLUENCE && dist > 0.001) {
            const proximity = 1 - dist / INFLUENCE; // 0..1
            // Energy: smoothstep target for an extra-natural wake curve.
            const target = proximity * proximity * (3 - 2 * proximity);
            p.energy += (target - p.energy) * ENERGY_RISE;
            // Magnetic: tiny nudge toward the cursor (quadratic falloff).
            const force = proximity * proximity * PULL;
            p.vx += (dx / dist) * force;
            p.vy += (dy / dist) * force;
          }
        }
        // Graceful decay back toward idle when the cursor is gone or far away.
        p.energy += (0 - p.energy) * ENERGY_DECAY;
        // Reaction velocity springs back toward zero (rest) and is damped, so
        // the magnetic nudge eases out smoothly — no snapping, no cutting.
        p.vx += (0 - p.vx) * VEL_SPRING;
        p.vy += (0 - p.vy) * VEL_SPRING;
        p.vx *= VEL_DAMPING;
        p.vy *= VEL_DAMPING;

        // 2) Ambient flow — the constant floating baseline. Runs ALWAYS, fully
        //    independent of the cursor. Each particle owns a slow flow vector
        //    that wobbles organically. Energy gently scales the drift speed
        //    and wobble so awake particles feel a little more lively.
        const wobbleMul = 1 + p.energy * (AWAKE_WOBBLE_MUL - 1);
        p.baseAngle += (Math.random() - 0.5) * AMBIENT_WOBBLE * wobbleMul;
        const driftMul = IDLE_DRIFT_MUL + p.energy * (AWAKE_DRIFT_MUL - IDLE_DRIFT_MUL);
        const flowVx = Math.cos(p.baseAngle) * p.baseSpeed * driftMul;
        const flowVy = Math.sin(p.baseAngle) * p.baseSpeed * driftMul;

        // Integrate: ambient drift + subtle magnetic reaction velocity.
        p.x += flowVx + p.vx;
        p.y += flowVy + p.vy;

        // Wrap around edges seamlessly so the field always stays full.
        if (p.x < -20) p.x = width + 20;
        else if (p.x > width + 20) p.x = -20;
        if (p.y < -20) p.y = height + 20;
        else if (p.y > height + 20) p.y = -20;

        // 3) Render. Idle = faded/subtle/low intensity. Awake = brighter,
        //    more visible, slightly larger glow (energy lifts alpha back up).
        //    Twinkle adds a gentle breathing shimmer to both states.
        p.twinkle += p.twinkleSpeed;
        const twinkleAlpha = p.baseAlpha + Math.sin(p.twinkle) * 0.08;
        // Energy lifts alpha well beyond idle on hover for a pronounced effect.
        const alpha = Math.max(0, Math.min(1, twinkleAlpha + p.energy * 0.85));
        const glow = p.size * (6 + p.energy * 2.4);

        ctx.globalAlpha = alpha;
        ctx.drawImage(sprite, p.x - glow / 2, p.y - glow / 2, glow, glow);
      }

      ctx.globalAlpha = 1;

      // Connection lines (network effect). Idle lines are clearly visible;
      // lines near energised particles brighten further on hover.
      for (let i = 0; i < particles.length; i++) {
        const a = particles[i];
        for (let j = i + 1; j < particles.length; j++) {
          const b = particles[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist2 = dx * dx + dy * dy;
          if (dist2 < CONNECT_DIST * CONNECT_DIST) {
            const dist = Math.sqrt(dist2);
            const base = (1 - dist / CONNECT_DIST) * 0.18;
            const energyBoost = Math.max(a.energy, b.energy) * 0.5;
            const alpha = Math.min(0.6, base + energyBoost);
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.strokeStyle = `rgba(73, 123, 249, ${alpha})`;
            ctx.lineWidth = 0.7;
            ctx.stroke();
          }
        }
      }

      rafId = requestAnimationFrame(draw);
    };

    setup();

    if (reduceMotion) {
      // Render a single calm frame for reduced-motion users (still floating
      // particles, just no animation loop).
      draw();
      running = false;
      cancelAnimationFrame(rafId);
    } else {
      draw();
    }

    let resizeTimer: ReturnType<typeof setTimeout>;
    const onResize = () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => setup(), 150);
    };

    // Track mouse across the whole window so the field reacts even when
    // hovering over hero content layered above the canvas.
    const onMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouseRef.current.tx = e.clientX - rect.left;
      mouseRef.current.ty = e.clientY - rect.top;
      if (!mouseRef.current.active) {
        // Snap on first entry to avoid a long glide from off-screen.
        mouseRef.current.x = mouseRef.current.tx;
        mouseRef.current.y = mouseRef.current.ty;
      }
      mouseRef.current.active = true;
    };
    const onLeave = () => {
      mouseRef.current.active = false;
      mouseRef.current.tx = -9999;
      mouseRef.current.ty = -9999;
    };

    window.addEventListener("resize", onResize);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseout", (e) => {
      if (!e.relatedTarget) onLeave();
    });

    return () => {
      running = false;
      cancelAnimationFrame(rafId);
      clearTimeout(resizeTimer);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("mousemove", onMove);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={className}
      style={{ pointerEvents: "none" }}
    />
  );
}
