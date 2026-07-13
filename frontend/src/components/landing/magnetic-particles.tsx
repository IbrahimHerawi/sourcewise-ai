"use client";

import { useEffect, useRef } from "react";

type Particle = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  baseAlpha: number;
  twinkle: number;
  twinkleSpeed: number;
};

/**
 * MagneticParticles
 *
 * A premium, mouse-reactive particle field rendered on a canvas.
 * - Dense, numerous particles float smoothly across the screen.
 * - The cursor acts as a subtle magnetic force that ATTRACTS nearby
 *   particles toward it with smooth easing (no repulsion, no snapping).
 * - Nearby particles are connected by faint lines for a network feel.
 * - Pre-rendered glow sprite keeps it fast even with hundreds of particles.
 * - Respects prefers-reduced-motion.
 */
export function MagneticParticles({ className }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mouseRef = useRef({ x: -9999, y: -9999, active: false, tx: -9999, ty: -9999 });

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
    // Uses normal (source-over) blending so it stays visible on a white background.
    const sprite = document.createElement("canvas");
    const SPRITE_SIZE = 48;
    sprite.width = SPRITE_SIZE;
    sprite.height = SPRITE_SIZE;
    const sctx = sprite.getContext("2d");
    if (sctx) {
      const half = SPRITE_SIZE / 2;
      const grad = sctx.createRadialGradient(half, half, 0, half, half, half);
      grad.addColorStop(0, "rgba(73, 123, 249, 0.95)");
      grad.addColorStop(0.18, "rgba(73, 123, 249, 0.7)");
      grad.addColorStop(0.5, "rgba(73, 123, 249, 0.16)");
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

      // Density: dense and numerous on larger screens, capped for perf.
      const area = width * height;
      const count = Math.min(320, Math.max(80, Math.floor(area / 4600)));
      particles = new Array(count);
      for (let i = 0; i < count; i++) {
        particles[i] = {
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.22,
          vy: (Math.random() - 0.5) * 0.22,
          size: Math.random() * 1.6 + 0.8,
          baseAlpha: Math.random() * 0.35 + 0.45,
          twinkle: Math.random() * Math.PI * 2,
          twinkleSpeed: Math.random() * 0.02 + 0.008,
        };
      }
    };

    const INFLUENCE = 230; // magnetic pull radius
    const PULL = 0.55; // attraction strength (gentle)
    const DAMPING = 0.93; // high damping => smooth easing, no harsh motion
    const DRIFT = 0.0008; // tiny ambient drift so particles keep floating
    const CONNECT_DIST = 138; // distance for connection lines

    const draw = () => {
      if (!running) return;
      ctx.clearRect(0, 0, width, height);

      const mouse = mouseRef.current;
      // ease the effective mouse position for an extra-smooth attractor
      mouse.x += (mouse.tx - mouse.x) * 0.12;
      mouse.y += (mouse.ty - mouse.y) * 0.12;

      // Particles (normal source-over blending; visible on white)
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];

        // Magnetic attraction toward cursor (smooth, no repulsion)
        if (mouse.active) {
          const dx = mouse.x - p.x;
          const dy = mouse.y - p.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < INFLUENCE && dist > 0.001) {
            const force = (1 - dist / INFLUENCE) * PULL;
            p.vx += (dx / dist) * force;
            p.vy += (dy / dist) * force;
          }
        }

        // Gentle ambient drift keeps particles slowly floating
        p.vx += (Math.random() - 0.5) * DRIFT;
        p.vy += (Math.random() - 0.5) * DRIFT;

        // Damping for smooth easing
        p.vx *= DAMPING;
        p.vy *= DAMPING;

        p.x += p.vx;
        p.y += p.vy;

        // Wrap around edges seamlessly
        if (p.x < -20) p.x = width + 20;
        else if (p.x > width + 20) p.x = -20;
        if (p.y < -20) p.y = height + 20;
        else if (p.y > height + 20) p.y = -20;

        // Twinkle alpha
        p.twinkle += p.twinkleSpeed;
        const alpha = Math.max(0, p.baseAlpha + Math.sin(p.twinkle) * 0.16);

        // Soft glow sprite (source-over keeps the brand-blue dot visible on white)
        const glow = p.size * 6;
        ctx.globalAlpha = alpha;
        ctx.drawImage(sprite, p.x - glow / 2, p.y - glow / 2, glow, glow);
      }

      ctx.globalAlpha = 1;

      // Connection lines (network effect)
      for (let i = 0; i < particles.length; i++) {
        const a = particles[i];
        for (let j = i + 1; j < particles.length; j++) {
          const b = particles[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist2 = dx * dx + dy * dy;
          if (dist2 < CONNECT_DIST * CONNECT_DIST) {
            const dist = Math.sqrt(dist2);
            const alpha = (1 - dist / CONNECT_DIST) * 0.2;
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
      // Render a single calm frame for reduced-motion users
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
        // snap on first entry to avoid a long glide from off-screen
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
