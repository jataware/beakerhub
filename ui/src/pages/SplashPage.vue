<template>
  <Teleport to="header .header-content">
        <nav class="nav-links">
          <Button text class="nav-features-link" @click="scrollToSection('features')">Features</Button>
          <Button text class="nav-domains-link" @click="scrollToSection('domains')">Scientific Domains</Button>
          <Button text class="login-button" as="router-link" :to="{name: 'login'}">Login</Button>
          <Button outlined class="try-cta-button" as="router-link" :to="{name: 'signup'}">
            <span class="try-text-full">Try BeakerHub</span>
            <span class="try-text-short">Sign Up</span>
          </Button>
          <Button text size="small" variant="link" as="a" href="https://github.com/jataware/beaker-notebook"
            target="_blank" rel="noopener" :title="'Open source Beaker Notebook project backing BeakerHub'"
            class="github-link">
            <i class="pi pi-github"></i>
          </Button>
        </nav>
  </Teleport>

  <div class="splash-page">

    <main class="splash-main">

      <section class="hero-section">

        <HeroSVGBackground />

        <div class="hero-content-centered">
          <div class="logo-section">
              <BeakerHubLogo class="logo"/>
              <h2 class="brand-name">BeakerHub</h2>
          </div>
          <h1 class="hero-title">
            Your AI-Powered Scientific Computational Notebook
          </h1>
          <p class="hero-subtitle">
            Transform your research with specialized AI agents that understand your field.
          </p>
          <div class="hero-actions">
            <Button size="large" class="primary-cta request-access-button" as="router-link" :to="{name: 'signup'}">
              Get Started
              <i class="pi pi-arrow-right"></i>
            </Button>
            <Button outlined size="large" @click="scrollToSection('domains')">
              Explore Domains
            </Button>
          </div>
        </div>
      </section>


      <section id="features" class="features-section">
        <div class="section-header">
          <h2 class="section-title">Powerful Features for Scientific Computing</h2>
          <p class="section-subtitle">Everything you need for advanced data analysis and research</p>
        </div>
        <div class="features-grid">
          <div class="feature-card">
            <div class="feature-card-inner">
              <div class="feature-card-front">
                <div class="feature-content">
                  <h3 class="feature-title">Specialized Scientific Agents</h3>
                  <p class="feature-description">
                    AI agents with access to scientific literature and specialized workflows, equipped with
                    domain-specific
                    tools, APIs, and databases. Your force multiplier for tackling complex research problems.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div class="feature-card">
            <div class="feature-card-inner">
              <div class="feature-card-front">
                <div class="feature-content">
                  <h3 class="feature-title">AI-Powered Interactive Notebooks</h3>
                  <p class="feature-description">
                    Full Jupyter compatibility allows you to use the tools you already know, imbued with scientific AI
                    superpowers.
                    Beaker is Jupyter for the AI era.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div class="feature-card">
            <div class="feature-card-inner">
              <div class="feature-card-front">
                <div class="feature-content">
                  <h3 class="feature-title">Intelligent Workflows</h3>
                  <p class="feature-description">
                    Customizable scientific workflows that adapt to your data and your needs.
                    From genomics pipelines to meteorological analysis, let Beaker handle repeatable analytical tasks.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div class="feature-card">
            <div class="feature-card-inner">
              <div class="feature-card-front">
                <div class="feature-content">
                  <h3 class="feature-title">Full Provenance for Reproducible Research</h3>
                  <p class="feature-description">
                    Beaker tracks the provenance for all data, literature, and methodologies used in your analysis so
                    you can easily reproduce your results.
                    Beaker provides extensive citations for complete transparency and explainable AI.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div class="feature-card">
            <div class="feature-card-inner">
              <div class="feature-card-front">
                <div class="feature-content">
                  <h3 class="feature-title">Customizable Data Exports</h3>
                  <p class="feature-description">
                    Export your analysis to multiple formats including custom reports tailored to your needs.
                    Beaker notebooks are exportable as Jupyter notebooks, allowing for easy sharing with collaborators.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div class="feature-card">
            <div class="feature-card-inner">
              <div class="feature-card-front">
                <div class="feature-content">
                  <h3 class="feature-title">Full Agent Customization</h3>
                  <p class="feature-description">
                    Completely customize your agent's context by providing it access to specific tools, APIs, databases,
                    and more.
                    Beaker agents can be easily reprompted for more narrow domain-specific tasks.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>


      <section class="demo-section">
        <div class="demo-container">
          <h2 class="demo-title">See BeakerHub in Action</h2>
          <div class="demo-visual">
            <div class="video-container">
              <video ref="demoVideo" class="demo-video" :class="{ 'playing': videoPlaying }" preload="metadata"
                @click="toggleVideo" @ended="handleVideoEnded">
                <source src="/videos/beaker_demo.mp4" type="video/mp4">
                Your browser does not support the video tag.
              </video>
              <div v-if="!videoPlaying" class="video-placeholder" @click="playVideo">
                <div class="placeholder-content">
                  <i class="pi pi-play-circle placeholder-icon"></i>
                  <span>Watch Demo</span>
                  <p class="placeholder-alt">BeakerHub interface showing specialized AI agents working on scientific
                    research</p>
                </div>
              </div>
              <!-- pause overlay -->
              <div v-if="videoPlaying && videoPaused" class="pause-overlay" @click="toggleVideo">
                <i class="pi pi-play-circle pause-icon"></i>
              </div>
            </div>
          </div>
        </div>
      </section>


      <section id="domains" class="domains-section">
        <div class="section-header">
          <h2 class="section-title">Scientific Domains</h2>
          <p class="section-subtitle domains-subtitle">
            Beaker is customizable to a huge number of scientific domains.
            Below are just some of the domains Beaker can support.
          </p>
        </div>
        <DomainsCarousel />
      </section>


      <section class="cta-section">
        <Card class="cta-card">
          <template #content>
            <div class="cta-content">
              <h2 class="cta-title">Ready to Accelerate Your Research?</h2>
              <p class="cta-description">
                Join researchers and data scientists who are already using BeakerHub
                to accelerate breakthrough research and solve complex scientific problems.
              </p>
              <Button size="large" class="primary-cta request-access-button responsive-button" as="router-link" :to="{name: 'signup'}">
                <span class="request-text-full">Get Started</span>
                <span class="request-text-short">Sign Up</span>
                <i class="pi pi-arrow-right"></i>
              </Button>
              <p class="cta-note">
                Create your account to access BeakerHub<span class="bullet-separator"> • </span><span class="beta-text">Currently in Beta</span>
              </p>
            </div>
          </template>
        </Card>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import Button from 'primevue/button';
import Card from 'primevue/card';
import { Teleport } from 'vue';

import HeroSVGBackground from '@/components/splash/HeroSVGBackground.vue';
import DomainsCarousel from '@/components/DomainsCarousel.vue';
import BeakerHubLogo from '@/components/BeakerHubLogo.vue';


const isDarkMode = ref(false);
const demoVideo = ref<HTMLVideoElement | null>(null);
const videoPlaying = ref(false);
const videoPaused = ref(false);


function scrollToSection(sectionId: string, useClass: boolean = false) {
  const element = useClass ? document.getElementsByClassName(sectionId)[0] : document.getElementById(sectionId);
  if (element) {
    const headerHeight = 20; // Even further reduced to scroll more down the page
    const elementPosition = (element as HTMLElement).offsetTop - headerHeight;

    window.scrollTo({
      top: elementPosition,
      behavior: 'smooth'
    });
  }
}

function playVideo() {
  if (demoVideo.value) {
    demoVideo.value.play().then(() => {
      videoPlaying.value = true;
      videoPaused.value = false;
    }).catch(error => {
      console.error("Error playing video:", error);
    });
  }
}

function toggleVideo() {
  if (demoVideo.value) {
    if (videoPlaying.value) {
      demoVideo.value.pause();
      videoPlaying.value = false;
      videoPaused.value = true;
    } else {
      demoVideo.value.play().then(() => {
        videoPlaying.value = true;
        videoPaused.value = false;
      }).catch(error => {
        console.error("Error playing video:", error);
      });
    }
  }
}

function handleVideoEnded() {
  videoPlaying.value = false;
  videoPaused.value = false;
}


</script>

<style lang="scss" scoped>
.splash-page {
  min-height: 100vh;
  width: 100%;
  max-width: 100vw;
  background: linear-gradient(135deg,
      var(--p-surface-a) 0%,
      rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.03) 25%,
      rgba(var(--p-blue-500-rgb, 59, 130, 246), 0.02) 50%,
      rgba(var(--p-purple-500-rgb, 168, 85, 247), 0.03) 75%,
      var(--p-surface-a) 100%);
  color: var(--p-text-color);
  position: relative;

  &::before {
    content: '';
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: radial-gradient(circle at 20% 20%,
        rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.05) 0%,
        transparent 50%),
      radial-gradient(circle at 80% 80%,
        rgba(var(--p-blue-500-rgb, 59, 130, 246), 0.04) 0%,
        transparent 50%),
      radial-gradient(circle at 40% 60%,
        rgba(var(--p-purple-500-rgb, 168, 85, 247), 0.03) 0%,
        transparent 50%);
    pointer-events: none;
    z-index: 0;
  }
}

.header-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 2rem 2rem;
  max-width: 1400px;
  margin: 0 auto;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 1rem;

  .theme-toggle {
    margin-left: 0.5rem;

    &:hover {
      color: var(--p-primary-color);
      background: rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.1);
    }

    i {
      font-size: 1.125rem;
    }
  }

  .github-link {
    margin-left: 0.5rem;
    text-decoration: none;

    &:hover {
      color: var(--p-primary-color);
      background: rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.1);
    }

    i {
      font-size: 1.125rem;
    }
  }

  .try-cta-button {
    border-color: var(--p-primary-color);
    text-decoration: none;
    white-space: nowrap;
    min-width: fit-content;

    .try-text-short {
      display: none;
    }

    // switch to short text on medium screens
    @media (max-width: 1024px) and (min-width: 769px) {
      .try-text-full {
        display: none;
      }

      .try-text-short {
        display: inline;
      }
    }

    // switch to short text on small screens
    @media (max-width: 768px) {
      .try-text-full {
        display: none;
      }

      .try-text-short {
        display: inline;
      }
    }
  }

  .login-button {
    text-decoration: none;
  }
}

.splash-main {
  .hero-section {
    position: relative;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 3rem 2rem 4rem;
    max-width: 1200px;
    margin: 0 auto;
    // min-height: 75vh;
    text-align: center;
    overflow: hidden;

    .hero-content-centered {
      position: relative;
      z-index: 1;

      .hero-title {
        font-size: 3.5rem;
        font-weight: 700;
        line-height: 1.1;
        margin-bottom: 1.5rem;
        color: var(--p-text-color);

        background: linear-gradient(135deg, var(--p-blue-600), var(--p-teal-500), var(--p-green-500));
        background-clip: text;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;

        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
      }

      .hero-subtitle {
        opacity: 0.8;
        margin-bottom: 2.7rem;
        margin-left: auto;
        margin-right: auto;
        font-family: system-ui;

        font-size: 2.5rem;
        max-width: 60rem;
        font-weight: 600;
        color: var(--p-blue-400);
      }

      .hero-actions {
        display: flex;
        gap: 1rem;
        flex-wrap: wrap;
        justify-content: center;

        .primary-cta {
          background: var(--p-primary-color);
          border-color: var(--p-primary-color);
          color: white;

          i {
            margin-left: 0.5rem;
          }
        }
      }
    }

    .beta-notice {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.5rem;
      margin-top: 2rem;
      padding: 1rem 2rem;
      background: rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.1);
      border: 1px solid rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.3);
      border-radius: 2rem;
      color: var(--p-primary-color);
      font-weight: 500;
      font-size: 0.875rem;

      i {
        font-size: 1rem;
      }
    }
  }

  .demo-section {
    padding: 4rem 2rem;
    max-width: 1200px;
    margin: 0 auto;
    text-align: center;

    .demo-title {
      font-size: 2rem;
      font-weight: 600;
      margin-bottom: 3rem;
      color: var(--p-text-color);
    }

    .demo-visual {
      .video-container {
        position: relative;
        width: 100%;
        margin: 0 auto;
        aspect-ratio: 16/10;
        border-radius: 1rem;
        overflow: hidden;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
        transition: transform 0.3s ease;

        &:hover {
          transform: scale(1.02);
        }

        .video-placeholder {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background: rgba(0, 0, 0, 0.7);
          border-radius: 1rem;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          z-index: 1;

          .placeholder-content {
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            color: white;
            text-align: center;
            padding: 2rem;
            width: 100%;
            height: 100%;

            .placeholder-icon {
              font-size: 3rem;
              margin-bottom: 1rem;
              color: var(--p-primary-color);
            }

            span {
              font-weight: 500;
              font-size: 1.125rem;
              margin-bottom: 0.5rem;
            }

            .placeholder-alt {
              font-size: 0.875rem;
              color: rgba(255, 255, 255, 0.8);
              margin: 0;
            }
          }
        }

        .demo-video {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          object-fit: cover;
          box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5);
          object-position: top;
          transition: transform 0.3s ease;

          &.playing {
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5);
            object-position: top;
          }
        }

        .pause-overlay {
          position: absolute;
          top: 0;
          left: 0;
          width: 100%;
          height: 100%;
          background: rgba(0, 0, 0, 0.7);
          border-radius: 1rem;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          z-index: 2;
          opacity: 0;
          transition: opacity 0.3s ease;

          &:hover {
            opacity: 1;
          }

          .pause-icon {
            font-size: 3rem;
            color: white;
          }
        }
      }
    }
  }

  .features-section,
  .domains-section,
  .use-cases-section,
  .how-it-works-section {
    padding: 6rem 2rem;
    max-width: 1200px;
    margin: 0 auto;
    position: relative;
    z-index: 1;

    .section-header {
      text-align: center;
      margin-bottom: 4rem;

      .section-title {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 1rem;
        color: var(--p-text-color);
      }

      .section-subtitle {
        font-size: 1.25rem;
        color: var(--text-color-secondary);
        max-width: 600px;
        margin: 0 auto;

        &.domains-subtitle {
          font-size: 1.7rem;
          max-width: 55rem;

          margin-top: 1.5rem;
        }
      }
    }
  }

  .features-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 2rem;

    @media (max-width: 768px) {
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 1rem;
    }

    @media (max-width: 480px) {
      grid-template-columns: 1fr;
      gap: 1rem;
    }

    .feature-card {
      perspective: 1000px;
      aspect-ratio: 1 / 1;
      position: relative;
      z-index: 2;

      @media (max-width: 768px) {
        aspect-ratio: unset;
        min-height: 300px;
      }

      // offset border patterns for each card
      &:nth-child(1) {
        --border-angle: 135deg;
        --glow-color-r: 59;
        --glow-color-g: 130;
        --glow-color-b: 246;
      }

      &:nth-child(2) {
        --border-angle: 225deg;
        --glow-color-r: 6;
        --glow-color-g: 182;
        --glow-color-b: 212;
      }

      &:nth-child(3) {
        --border-angle: 315deg;
        --glow-color-r: 16;
        --glow-color-g: 185;
        --glow-color-b: 129;
      }

      &:nth-child(4) {
        --border-angle: 45deg;
        --glow-color-r: 139;
        --glow-color-g: 92;
        --glow-color-b: 246;
      }

      &:nth-child(5) {
        --border-angle: 180deg;
        --glow-color-r: 59;
        --glow-color-g: 130;
        --glow-color-b: 246;
      }

      &:nth-child(6) {
        --border-angle: 270deg;
        --glow-color-r: 6;
        --glow-color-g: 182;
        --glow-color-b: 212;
      }

      .feature-card-inner {
        position: relative;
        width: 100%;
        height: 100%;
        text-align: center;
        transition: all 2.2s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        border-radius: 1rem;

        @media (max-width: 768px) {
          height: auto;
          min-height: 100%;
        }

        border: 3px solid transparent;
        // subtle border with offset pattern
        background:
          linear-gradient(var(--p-surface-b), var(--p-surface-b)) padding-box,
          linear-gradient(var(--border-angle, 135deg),
            var(--p-blue-500),
            var(--p-cyan-500),
            var(--p-green-500),
            var(--p-violet-500),
            var(--p-blue-500)) border-box;

        box-shadow:
          0 4px 6px -1px rgba(0, 0, 0, 0.1),
          0 0 20px rgba(var(--glow-color-r, 59), var(--glow-color-g, 130), var(--glow-color-b, 246), 0.1),
          inset 0 1px 0 color-mix(in srgb, var(--p-surface-0) 8%, transparent);
      }

      .feature-card-front,
      .feature-card-back {
        width: 100%;
        height: 100%;
        border-radius: 0.5rem;
        overflow: hidden;
      }

      .feature-card-front {
        opacity: 1;
        transform: translateZ(0) scale(1);
        background: transparent;
        display: flex;
        align-items: center;
        justify-content: center;

        .feature-content {
          padding: 2rem;
          position: relative;
          z-index: 1;
          text-align: left;

          @media (max-width: 768px) {
            padding: 1.75rem 1.25rem 1.25rem 1.25rem;
          }

          .user-benefit {
            font-size: 0.875rem;
            font-weight: 500;
            color: var(--p-primary-color);
            text-transform: uppercase;
            font-style: italic;
            letter-spacing: 0.05em;
            margin-bottom: 0.75rem;
            opacity: 0.8;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
          }

          .feature-title {
            margin-top: 0;
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: var(--p-text-color);
          }

          .feature-description {
            color: var(--text-color-secondary);
            line-height: 1.6;
          }
        }
      }

      .feature-card-back {
        opacity: 0;
        transform: translateZ(-50px) scale(0.9);
        background: var(--p-surface-c);
        display: flex;
        align-items: center;
        justify-content: center;

        .feature-media {
          width: 100%;
          height: 100%;
          position: relative;
          overflow: hidden;

          // shimmer overlay
          &::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(45deg,
                color-mix(in srgb, var(--p-blue-500) 15%, transparent),
                transparent 20%,
                transparent 40%,
                color-mix(in srgb, var(--p-green-500) 10%, transparent) 60%,
                transparent 80%,
                color-mix(in srgb, var(--p-violet-500) 12%, transparent));
            pointer-events: none;
            z-index: 1;
            opacity: 0.7;
          }
        }
      }
    }
  }
}

.use-cases-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 2rem;

  .use-case-card {
    .use-case-header {
      display: flex;
      align-items: center;
      gap: 1rem;
      padding: 1rem;

      .use-case-icon {
        font-size: 2rem;
        color: var(--p-primary-color);
      }

      h3 {
        margin: 0;
        font-size: 1.25rem;
        font-weight: 600;
      }
    }

    .use-case-content {
      .request {
        font-style: italic;
        color: var(--text-color-secondary);
        margin-bottom: 1rem;
      }

      .arrow {
        text-align: center;
        margin: 1rem 0;
        color: var(--p-primary-color);
      }

      .solution {
        line-height: 1.6;
      }
    }
  }
}


.workflow-steps {
  .workflow-step {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 2rem;
    align-items: center;
    margin-bottom: 4rem;

    &.reverse {
      grid-template-columns: auto 1fr auto;

      .step-content {
        order: 2;
        text-align: right;
      }

      .step-visual {
        order: 1;
      }

      .step-number {
        order: 3;
      }
    }

    .step-number {
      width: 4rem;
      height: 4rem;
      border-radius: 50%;
      background: var(--p-primary-color);
      color: white;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.5rem;
      font-weight: 600;
    }

    .step-content {
      .step-title {
        font-size: 1.5rem;
        font-weight: 600;
        margin-bottom: 1rem;
      }

      .step-description {
        color: var(--text-color-secondary);
        line-height: 1.6;
      }
    }

    .step-visual {
      width: 300px;
      height: 200px;
      border-radius: 0.5rem;
      overflow: hidden;
      background: var(--p-surface-c);
    }
  }
}

.cta-section {
  padding: 4rem 2rem;
  max-width: 800px;
  margin: 0 auto;
  position: relative;
  z-index: 1;

  .cta-card {
    background: linear-gradient(135deg, var(--p-primary-color), var(--p-blue-600));
    color: white;
    text-align: center;
    position: relative;
    z-index: 2;

    .cta-content {
      padding: 2rem;

      .cta-title {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 1rem;
        color: white;
        opacity: 1;
      }

      .cta-description {
        font-size: 1.125rem;
        opacity: 0.9;
        margin-bottom: 2rem;
      }

      .primary-cta {
        background: white;
        color: var(--p-primary-color);
        border: none;

        i {
          margin-left: 0.5rem;
        }
      }

      .cta-note {
        margin-top: 1rem;
        opacity: 0.8;
        font-size: 0.875rem;

        .beta-text {
          white-space: nowrap;
        }

        .bullet-separator {
          white-space: nowrap;
        }
      }
    }
  }
}

.placeholder-image {
  position: relative;
  background: var(--p-surface-c);
  display: flex;
  align-items: center;
  justify-content: center;

  .placeholder-content {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    color: var(--text-color-secondary);
    text-align: center;
    padding: 2rem;
    width: 100%;
    height: 100%;

    .placeholder-icon {
      font-size: 3rem;
      margin-bottom: 1rem;
      color: var(--p-primary-color);
    }

    span {
      font-weight: 500;
      font-size: 1.125rem;
      margin-bottom: 0.5rem;
    }

    .placeholder-alt {
      font-size: 0.875rem;
      color: var(--text-color-secondary);
      margin: 0;
      opacity: 0.8;
    }
  }

  &:hover .placeholder-content {
    background: var(--p-surface-d);

    .placeholder-icon {
      color: var(--p-primary-600);
      transform: scale(1.1);
    }
  }
}

@media (max-width: 768px) {
  .splash-header {
    .header-nav {
      flex-direction: column;
      gap: unset;
      padding: 1rem 0.5rem;

      .nav-links {
        flex-wrap: wrap;
        justify-content: center;
        align-items: center;
        gap: unset;
        width: 100%;

        .p-button {
          font-size: 0.875rem;
          padding: 0.5rem 0.75rem;
          display: flex;
          align-items: center;
          justify-content: center;
          height: 2.5rem;
        }

        .theme-toggle,
        .github-link {
          font-size: 0.875rem;
          padding: 0.5rem;
          min-width: 2.5rem;
          height: 2.5rem;
          display: flex;
          align-items: center;
          justify-content: center;
        }
      }
    }
  }

  .hero-section {
    padding: 4rem 1rem 2rem !important;
    min-height: 60vh !important;

    .hero-content-centered .hero-title {
      font-size: 2.5rem !important;
    }

    .beta-notice {
      padding: 0.75rem 1.5rem !important;
      font-size: 0.8rem !important;
    }
  }

  .demo-section {
    padding: 2rem 1rem !important;

    .demo-title {
      font-size: 1.5rem !important;
      margin-bottom: 2rem !important;
    }
  }

  .splash-footer .footer-content {
    grid-template-columns: 1fr !important;
    gap: 2rem;
  }
}

.beaker-agent-notebook {
  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5);
    object-position: left;
    transform: scale(1.1);
  }
}

.workflow-steps {
  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    object-position: left;
  }
}

.beaker-export-own {
  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: top;
  }
}

.beaker-edit-cells {
  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: left;
    transform: scale(1.12);
  }
}

.customize-agent {
  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: left;
  }
}


.retrieval-training {
  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: left;
    transform: scale(1.1);
  }
}

.cta-content .request-access-button {
  text-decoration: none;
  transition: all 0.3s ease;
  // min-width: 320px; /* Minimum width to prevent shifting but allow natural sizing */
  margin: 0 auto; /* Center the button */
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;

  .request-text-short {
    display: none;
  }

  &.showing-email {
    .email-address {
      font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
      font-weight: 600;
      background: rgba(255, 255, 255, 0.2);
      padding: 0.25rem 0.5rem;
      border-radius: 0.25rem;
      border: 1px solid rgba(255, 255, 255, 0.3);
      transition: all 0.2s ease;
      user-select: text; /* Allow text selection */
      cursor: text; /* Show text cursor when hovering over email */
    }

    i.pi-copy {
      transition: transform 0.2s ease;
      cursor: pointer;

      &:hover {
        transform: scale(1.1);
      }
    }

    &:hover .email-address {
      background: rgba(255, 255, 255, 0.3);
      border-color: rgba(255, 255, 255, 0.5);
    }

    &:active .email-address {
      background: rgba(255, 255, 255, 0.4);
    }
  }
}

/* Keep the hero section button styles separate */
.hero-actions .request-access-button {
  text-decoration: none;

  &.showing-email .email-address {
    user-select: text; /* Allow text selection */
    cursor: text; /* Show text cursor when hovering over email */
  }
}

.beaker-dark {
  .request-access-button {
    text-shadow: none;

    &.showing-email .email-address {
      background: rgba(0, 0, 0, 0.2);
      border-color: rgba(255, 255, 255, 0.2);
    }

    &.showing-email:hover .email-address {
      background: rgba(0, 0, 0, 0.3);
      border-color: rgba(255, 255, 255, 0.3);
    }

    &.showing-email:active .email-address {
      background: rgba(0, 0, 0, 0.4);
    }
  }
}

@media (max-width: 768px) {
  .responsive-button {
    /* small button style for smaller button on mobile */
    padding: 0.75rem 1rem !important;
    font-size: 0.875rem !important;
  }
}

@media (max-width: 405px) {
  .splash-header {
    .header-nav {
      .nav-links {
        gap: 0.5rem;
        margin-top: 0.5rem;
        justify-content: right;

        .nav-features-link,
        .nav-domains-link {
          display: none;
        }
      }
    }
  }

  .cta-section .cta-card .cta-content {
    padding-left: 0.5rem;
    padding-right: 0.5rem;

    .request-access-button.responsive-button {
      .request-text-full {
        display: none;
      }
      .request-text-short {
        display: inline;
      }
    }

    .cta-note {
      .bullet-separator {
        display: none;
      }

      .beta-text {
        display: block;
        margin-top: 0.25rem;
      }
    }
  }
}

.logo-section {
    --size: 6rem;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 1rem;
    padding: 0rem 0 2rem 0;

    .logo {
      --logo-size: calc(var(--size) * 4/3);
      height: var(--logo-size);
      width: var(--logo-size);
    }
}

.brand-name {
    font-size: var(--size);
    font-weight: 700;
    background: linear-gradient(135deg, var(--p-primary-color), var(--p-blue-500));
    background-clip: text;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
}


@media (max-width: 768px) {
    .logo-section {
        .brand-name {
            font-size: 1.5rem;
        }
    }
}

</style>
