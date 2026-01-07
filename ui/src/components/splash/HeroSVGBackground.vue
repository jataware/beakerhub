<template>
  <div class="hero-background">
    <svg viewBox="0 0 2000 1000" xmlns="http://www.w3.org/2000/svg" class="hero-neural-svg">
      <defs>
        <radialGradient id="centerGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="rgba(59, 130, 246, 0.25)" />
          <stop offset="40%" stop-color="rgba(20, 184, 166, 0.15)" />
          <stop offset="70%" stop-color="rgba(34, 197, 94, 0.1)" />
          <stop offset="100%" stop-color="transparent" />
        </radialGradient>

        <linearGradient id="connectionLine" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="rgba(59, 130, 246, 0.4)" />
          <stop offset="50%" stop-color="rgba(20, 184, 166, 0.3)" />
          <stop offset="100%" stop-color="rgba(34, 197, 94, 0.25)" />
        </linearGradient>

        <linearGradient id="connectionLine2" x1="100%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="rgba(20, 184, 166, 0.35)" />
          <stop offset="50%" stop-color="rgba(34, 197, 94, 0.25)" />
          <stop offset="100%" stop-color="rgba(59, 130, 246, 0.3)" />
        </linearGradient>

        <radialGradient id="nodeGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="rgba(59, 130, 246, 0.6)" />
          <stop offset="100%" stop-color="transparent" />
        </radialGradient>

        <!-- glow filter -->
        <filter id="softGlow" x="-100%" y="-100%" width="300%" height="300%">
          <feGaussianBlur stdDeviation="3" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>

        <filter id="strongGlow" x="-100%" y="-100%" width="300%" height="300%">
          <feGaussianBlur stdDeviation="5" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <!-- background -->
      <rect width="2000" height="1000" fill="transparent" />

      <!-- overlapping central glows -->
      <ellipse cx="1000" cy="500" rx="800" ry="450" fill="url(#centerGlow)" opacity="0.8" />
      <ellipse cx="1000" cy="500" rx="500" ry="250" fill="url(#centerGlow)" opacity="0.6" />
      <ellipse cx="1000" cy="500" rx="900" ry="550" fill="url(#centerGlow)" opacity="0.4" />

      <!-- node points span full width -->
      <circle cx="100" cy="200" r="6" fill="rgba(59, 130, 246, 0.7)" filter="url(#strongGlow)" />
      <circle cx="1650" cy="200" r="6" fill="rgba(20, 184, 166, 0.7)" filter="url(#strongGlow)" />
      <circle cx="50" cy="400" r="5" fill="rgba(34, 197, 94, 0.6)" filter="url(#strongGlow)" />
      <circle cx="1800" cy="400" r="5" fill="rgba(59, 130, 246, 0.6)" filter="url(#strongGlow)" />
      <circle cx="80" cy="700" r="5.5" fill="rgba(20, 184, 166, 0.6)" filter="url(#strongGlow)" />
      <circle cx="1750" cy="700" r="5.5" fill="rgba(34, 197, 94, 0.6)" filter="url(#strongGlow)" />

      <!-- network, full width -->
      <circle cx="300" cy="150" r="4" fill="rgba(59, 130, 246, 0.5)" filter="url(#softGlow)" />
      <circle cx="1500" cy="150" r="4" fill="rgba(20, 184, 166, 0.5)" filter="url(#softGlow)" />
      <circle cx="200" cy="350" r="3" fill="rgba(34, 197, 94, 0.4)" />
      <circle cx="1600" cy="350" r="3" fill="rgba(59, 130, 246, 0.4)" />
      <circle cx="150" cy="600" r="3" fill="rgba(20, 184, 166, 0.4)" />
      <circle cx="1700" cy="600" r="3" fill="rgba(34, 197, 94, 0.4)" />
      <circle cx="350" cy="800" r="4" fill="rgba(59, 130, 246, 0.5)" filter="url(#softGlow)" />
      <circle cx="1450" cy="800" r="4" fill="rgba(20, 184, 166, 0.5)" filter="url(#softGlow)" />

      <!-- corner and far edge nodes -->
      <circle cx="20" cy="100" r="3" fill="rgba(34, 197, 94, 0.4)" />
      <circle cx="1880" cy="100" r="3" fill="rgba(59, 130, 246, 0.4)" />
      <circle cx="20" cy="900" r="3" fill="rgba(20, 184, 166, 0.4)" />
      <circle cx="1880" cy="900" r="3" fill="rgba(34, 197, 94, 0.4)" />

      <!-- wide distribution nodes -->
      <circle cx="400" cy="300" r="2.5" fill="rgba(59, 130, 246, 0.3)" />
      <circle cx="800" cy="300" r="2.5" fill="rgba(20, 184, 166, 0.3)" />
      <circle cx="1200" cy="300" r="2.5" fill="rgba(34, 197, 94, 0.3)" />
      <circle cx="1600" cy="300" r="2.5" fill="rgba(59, 130, 246, 0.3)" />
      <circle cx="500" cy="650" r="2.5" fill="rgba(34, 197, 94, 0.3)" />
      <circle cx="1000" cy="650" r="2.5" fill="rgba(59, 130, 246, 0.3)" />
      <circle cx="1300" cy="650" r="2.5" fill="rgba(20, 184, 166, 0.3)" />
      <circle cx="1700" cy="650" r="2.5" fill="rgba(34, 197, 94, 0.3)" />

      <!-- energy pulses - centered in viewBox -->
      <!-- Note: The `will-change` style rule should stay defined on these elements to match them to the circle's lifetime. -->
      <!--       for more information see https://developer.mozilla.org/en-US/docs/Web/CSS/will-change#via_stylesheet -->
      <circle style="will-change: transform, opacity, r;" cx="1000" cy="500" r="120" fill="none" stroke="rgba(59, 130, 246, 0.2)" stroke-width="1.2" opacity="0.8">
        <animate attributeName="r" values="120;180;120" dur="6s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.8;0.3;0.8" dur="6s" repeatCount="indefinite" />
      </circle>

      <circle style="will-change: transform, opacity, r;" cx="1000" cy="500" r="180" fill="none" stroke="rgba(20, 184, 166, 0.15)" stroke-width="1" opacity="0.6">
        <animate attributeName="r" values="180;250;180" dur="8s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.6;0.2;0.6" dur="8s" repeatCount="indefinite" />
      </circle>

      <circle style="will-change: transform, opacity, r;" cx="1000" cy="500" r="250" fill="none" stroke="rgba(34, 197, 94, 0.1)" stroke-width="1" opacity="0.4">
        <animate attributeName="r" values="250;320;250" dur="10s" repeatCount="indefinite" />
        <animate attributeName="opacity" values="0.4;0.1;0.4" dur="10s" repeatCount="indefinite" />
      </circle>
    </svg>
  </div>
</template>

<style lang="scss" scoped>
.hero-background {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 0;
  pointer-events: none;

  .hero-neural-svg {
    width: 100%;
    height: 100%;
    object-fit: cover;
    opacity: 1.0;
  }
}
</style>
