<template>
  <div class="domains-carousel" @mouseenter="stopAutoScroll" @mouseleave="startAutoScroll">
    <div class="carousel-container">
      <!-- Navigation Arrows -->
      <button
        v-if="shouldShowArrows"
        class="carousel-arrow carousel-arrow-left"
        @click="previousSlide"
        :disabled="isTransitioning || !canGoPrevious"
        aria-label="Previous domains"
      >
        <i class="pi pi-chevron-left"></i>
      </button>

      <button
        v-if="shouldShowArrows"
        class="carousel-arrow carousel-arrow-right"
        @click="nextSlide"
        :disabled="isTransitioning || !canGoNext"
        aria-label="Next domains"
      >
        <i class="pi pi-chevron-right"></i>
      </button>

      <div
        class="carousel-track"
        :style="{
          transform: `translateX(-${getTransformValue()}px)`,
          '--card-width': `${visibleCardsInfo.cardWidth}px`
        }"
      >
        <Card :class="['domain-card', domain.className]" v-for="(domain, index) in domains" :key="`original-${index}`">
          <template #content>
            <div class="domain-content">
              <div class="domain-icon" :class="domain.iconClass">
                <component :is="domain.iconComponent" />
              </div>
              <h3 class="domain-title">{{ domain.title }}</h3>
              <p class="domain-description">
                {{ domain.description }}
              </p>
              <div class="use-case-highlight">
                <strong>Example:</strong> {{ domain.example }}
              </div>
              <div class="domain-tools">
                <Tag v-for="tool in domain.tools" :key="tool" :value="tool" />
              </div>
            </div>
          </template>
        </Card>

        <Card :class="['domain-card', domain.className]" v-for="(domain, index) in domains" :key="`duplicate-${index}`">
          <template #content>
            <div class="domain-content">
              <div class="domain-icon" :class="domain.iconClass">
                <component :is="domain.iconComponent" />
              </div>
              <h3 class="domain-title">{{ domain.title }}</h3>
              <p class="domain-description">
                {{ domain.description }}
              </p>
              <div class="use-case-highlight">
                <strong>Example:</strong> {{ domain.example }}
              </div>
              <div class="domain-tools">
                <Tag v-for="tool in domain.tools" :key="tool" :value="tool" />
              </div>
            </div>
          </template>
        </Card>
      </div>
    </div>

    <div class="carousel-indicators">
      <button
        v-for="(domain, index) in domains"
        :key="index"
        class="carousel-dot"
        :class="{ active: currentIndex === index }"
        @click="goToSlide(index)"
        :aria-label="`Go to ${domain.title}`"
      ></button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import Card from 'primevue/card';
import Tag from 'primevue/tag';
import DataScienceIcon from './icons/DataScienceIcon.vue';
import BiomedicalIcon from './icons/BiomedicalIcon.vue';
import WeatherIcon from './icons/WeatherIcon.vue';
import WildfireIcon from './icons/WildfireIcon.vue';
import GeospatialIcon from './icons/GeospatialIcon.vue';
import CustomDomainIcon from './icons/CustomDomainIcon.vue';

const currentIndex = ref(0);
const autoScrollInterval = ref<NodeJS.Timeout | null>(null);
const isTransitioning = ref(false);

const domains = ref([
  {
    iconComponent: DataScienceIcon,
    iconClass: 'data-science',
    className: 'data-science-card',
    title: 'Data Science',
    description: 'Advanced statistical analysis, machine learning, and data visualization. Trained on data science methodologies with comprehensive Python ecosystem support.',
    example: '"Perform time series analysis on the loaded sales data, identify trends and seasonal patterns, then build predictive models with automated hyperparameter tuning and feature selection."',
    tools: ['pandas', 'scikit-learn', 'matplotlib', 'seaborn']
  },
  {
    iconComponent: WeatherIcon,
    iconClass: 'weather',
    className: 'weather-card',
    title: 'Meteorological Analysis',
    description: 'Atmospheric science, weather forecasting, and environmental data analysis. Access to NOAA, ECMWF, NASA data sources and specialized meteorological tools.',
    example: '"Fetch historical weather data from OpenMeteo API for multiple European cities, analyze precipitation patterns using ECMWF models, and create interactive weather maps with forecast visualization."',
    tools: ['NOAA PSL', 'ECMWF', 'xarray', 'cartopy']
  },
  {
    iconComponent: BiomedicalIcon,
    iconClass: 'biomedical',
    className: 'biomedical-card',
    title: 'Biomedical Research',
    description: 'Bioinformatics, genomics, proteomics, and drug discovery research. Connected to GDC, Census Health Surveys, AlphaGenome and other databases with specialized analysis workflows.',
    example: '"Query the GDC for cases of myeloid leukemia with a JAK2 somatic mutation and return the results as a pandas dataframe."',
    tools: ['CDA API', 'robokop', 'cBioPortal', 'GRAS']
  },
  {
    iconComponent: WildfireIcon,
    iconClass: 'wildfire',
    className: 'wildfire-card',
    title: 'Wildfire Analysis',
    description: 'Comprehensive wildfire research and geospatial analysis across multiple regions and datasets. Access to fire perimeter databases, historical burn data, and specialized wildfire modeling tools.',
    example: '"Analyze wildfire patterns across the Western United States from 1950-2023, create interactive maps with fire cause analysis, and correlate burn severity with terrain and weather data."',
    tools: ['USGS Structure DB', 'GeoPandas', 'Folium', 'Cartopy']
  },
  {
    iconComponent: GeospatialIcon,
    iconClass: 'geospatial',
    className: 'geospatial-card',
    title: 'Geospatial Intelligence & Critical Minerals',
    description: 'Comprehensive geospatial analysis of global critical mineral resources, mining locations, and geopolitical supply chains. Access to USGS MRDS database, ACLED conflict data, and global trade flows with specialized mapping and visualization tools.',
    example: '"Create an interactive map of lithium mining operations in Africa with conflict zones overlay, showing Chinese investment patterns and trade routes to major ports, including supply chain vulnerability analysis."',
    tools: ['USGS MRDS', 'ACLED API', 'Folium', 'GeoPandas', 'SAIS-CARI', 'Wikidata']
  },
  {
    iconComponent: CustomDomainIcon,
    iconClass: 'custom-domain',
    className: 'custom-domain-card',
    title: 'Your Custom Domain',
    description: 'Beaker is completely customizable to meet your organization\'s unique research needs. We can configure specialized agents for any scientific domain with custom tools, APIs, and data sources.',
    example: '"Build a custom agent for your specific research domain with tailored workflows, specialized databases, and domain-specific analysis tools designed for your team\'s unique requirements."',
    tools: ['Custom APIs', 'Your Data', 'Specialized Tools', 'Domain Expertise']
  }
]);

// calculate how many cards should be visible and their width
const getVisibleCardsInfo = () => {
  const containerPadding = 64; // 2rem padding on each side ~= 64px
  const availableWidth = window.innerWidth - containerPadding;
  const gap = 24; // 1.5rem gap ~= 24px
  const minCardWidth = 365; // minimum card width
  const maxCardWidth = 400; // maximum card width

  if (window.innerWidth <= 768) { // mobile
    // account for border/ spacing issues - reduce by 11px
    const mobileCardWidth = availableWidth - 11;
    return {
      visibleCards: 1,
      cardWidth: mobileCardWidth,
      cardWidthWithGap: mobileCardWidth
    };
  }

  if (window.innerWidth <= 1200) { // tablet
    const cardWidth = (availableWidth - gap) / 2;
    return {
      visibleCards: 2,
      cardWidth: cardWidth,
      cardWidthWithGap: cardWidth + gap
    };
  }

  let visibleCards = 3; // default to 3
  let cardWidth = 365; // default card width

  visibleCards = 3;
  cardWidth = Math.max(minCardWidth, Math.min(maxCardWidth, (availableWidth - (gap * 2)) / 3));

  return {
    visibleCards,
    cardWidth,
    cardWidthWithGap: cardWidth + gap
  };
};

const visibleCardsInfo = ref(getVisibleCardsInfo());
const cardWidthInPixels = ref(visibleCardsInfo.value.cardWidthWithGap);

// computed properties for arrow visibility
const shouldShowArrows = computed(() => {
  return visibleCardsInfo.value.visibleCards < domains.value.length;
});

const canGoPrevious = computed(() => {
  if (!shouldShowArrows.value) return false;
  return true;
});

const canGoNext = computed(() => {
  if (!shouldShowArrows.value) return false;
  return true;
});

function startAutoScroll() {
  stopAutoScroll();
  autoScrollInterval.value = setInterval(() => {
    nextSlide();
  }, 4000);
}

function stopAutoScroll() {
  if (autoScrollInterval.value) {
    clearInterval(autoScrollInterval.value);
    autoScrollInterval.value = null;
  }
}

function nextSlide() {
  if (isTransitioning.value) return;

  const info = visibleCardsInfo.value;

  // If all cards fit in viewport, don't allow navigation
  if (info.visibleCards >= domains.value.length) {
    return;
  }

  isTransitioning.value = true;
  const cardsToAdvance = 1;

  currentIndex.value += cardsToAdvance;

  if (currentIndex.value >= domains.value.length) {
    setTimeout(() => {
      const track = document.querySelector('.carousel-track') as HTMLElement;
      if (track) {
        track.style.transition = 'none';
        currentIndex.value = currentIndex.value - domains.value.length;
        requestAnimationFrame(() => {
          track.style.transition = 'transform 0.5s ease-in-out';
          isTransitioning.value = false;
        });
      } else {
        isTransitioning.value = false;
      }
    }, 500);
  } else {
    setTimeout(() => {
      isTransitioning.value = false;
    }, 500);
  }

  startAutoScroll();
}

function previousSlide() {
  if (isTransitioning.value) return;

  const info = visibleCardsInfo.value;

  // if all cards fit in viewport, don't allow navigation
  if (info.visibleCards >= domains.value.length) {
    return;
  }

  isTransitioning.value = true;
  const cardsToAdvance = 1;

  if (currentIndex.value - cardsToAdvance < 0) {
    // we're going below 0, seamlessly jump to equivalent position in duplicates
    const track = document.querySelector('.carousel-track') as HTMLElement;
    if (track) {
      track.style.transition = 'none';
      currentIndex.value = currentIndex.value + domains.value.length - cardsToAdvance;
      requestAnimationFrame(() => {
        track.style.transition = 'transform 0.5s ease-in-out';
        isTransitioning.value = false;
      });
    } else {
      isTransitioning.value = false;
    }
  } else {
    currentIndex.value -= cardsToAdvance;
    setTimeout(() => {
      isTransitioning.value = false;
    }, 500);
  }

  startAutoScroll();
}

function goToSlide(index: number) {
  if (isTransitioning.value || index === currentIndex.value) return;

  const info = visibleCardsInfo.value;

  // if all cards fit in viewport, don't allow navigation
  // we duploicate cards to allow for infinite feel
  if (info.visibleCards >= domains.value.length * 2) {
    return;
  }

  isTransitioning.value = true;
  const maxIndex = Math.max(0, domains.value.length * 2 - info.visibleCards);
  currentIndex.value = Math.min(index, maxIndex);

  setTimeout(() => {
    isTransitioning.value = false;
  }, 500);
}

// calculate transform value based on current index and card width in pixels
const getTransformValue = () => {
  const info = visibleCardsInfo.value;

  // if all cards fit in viewport, center them (no transform needed)
  if (info.visibleCards >= domains.value.length * 2) {
    return 0;
  }

  // Mobile-specific logic: position cards exactly to show one full card
  if (window.innerWidth <= 768) {
    // On mobile, move by the same calculated card width
    // Use same calculation as getVisibleCardsInfo for consistency
    const mobileCardWidth = (window.innerWidth - 64) - 10; // container width minus buffer
    return currentIndex.value * mobileCardWidth; // no gap since mobile cards have gap:0
  }

  // Desktop/tablet: use existing logic
  return currentIndex.value * cardWidthInPixels.value;
};

// handle window resize
const updateCardWidth = () => {
  visibleCardsInfo.value = getVisibleCardsInfo();
  cardWidthInPixels.value = visibleCardsInfo.value.cardWidthWithGap;

  // Clamp current index to valid range
  const info = visibleCardsInfo.value;
  if (info.visibleCards >= domains.value.length * 2) {
    currentIndex.value = 0;
  } else {
    const maxIndex = Math.max(0, domains.value.length * 2 - info.visibleCards);
    currentIndex.value = Math.min(currentIndex.value, maxIndex);
  }
};

onMounted(() => {
  startAutoScroll();
  window.addEventListener('resize', updateCardWidth);
});

onUnmounted(() => {
  stopAutoScroll();
  window.removeEventListener('resize', updateCardWidth);
});
</script>

<style lang="scss" scoped>
.domains-carousel {
  overflow: hidden;
  width: 100%;

  padding: 2rem; // should be 0 on mobile
  @media (max-width: 768px) {
    padding: 0;
  }

  .carousel-container {
    position: relative;
    width: 100%;
  }

  .carousel-arrow {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    z-index: 10;
    background: var(--p-surface-a);
    border: 2px solid var(--p-primary-color);
    border-radius: 50%;
    width: 3.5rem;
    height: 3.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.3s ease;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
    color: var(--p-primary-color);
    backdrop-filter: blur(10px);

    &:hover:not(:disabled) {
      background: var(--p-primary-color);
      color: white;
      transform: translateY(-50%) scale(1.1);
      box-shadow: 0 8px 25px rgba(0, 0, 0, 0.2);
    }

    &:disabled {
      opacity: 0.4;
      cursor: not-allowed;
      background: var(--p-surface-b);
      border-color: var(--p-surface-border);
      color: var(--p-text-color-secondary);
    }


    i {
      font-size: 1.4rem;
      font-weight: bold;
    }
  }

  .carousel-arrow-left {
    left: -1.75rem;

    @media (max-width: 768px) {
      left: 0.25rem;
      width: 3rem;
      height: 3rem;
    }
  }

  .carousel-arrow-right {
    right: -1.75rem;

    @media (max-width: 768px) {
      right: 0.25rem;
      width: 3rem;
      height: 3rem;
    }
  }

  .carousel-indicators {
    display: flex;
    justify-content: center;
    gap: 0.5rem;
    margin-top: 2rem;
    padding: 0 1rem;
    padding-bottom: 0.25rem;
  }

  .carousel-dot {
    width: 0.75rem;
    height: 0.75rem;
    border-radius: 50%;
    border: none;
    background: var(--p-surface-border);
    cursor: pointer;
    transition: all 0.3s ease;

    &:hover {
      background: var(--p-primary-color);
      transform: scale(1.2);
    }

    &.active {
      background: var(--p-primary-color);
      transform: scale(1.3);
    }

  }

  .carousel-track {
    display: flex;
    transition: transform 0.5s ease-in-out;
    gap: 1.5rem;

    @media (max-width: 768px) {
      gap: 0; // no gap on mobile since cards are full width
    }
  }

  .domain-card {
    flex: 0 0 var(--card-width, 365px); // use dynamic width from CSS variable
    width: var(--card-width, 365px);
    max-width: var(--card-width, 365px);
    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    background: var(--p-surface-a);
    border: 1px solid var(--p-surface-border);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
    overflow: hidden;
    position: relative;
    z-index: 2;

    // ============================================
    // TWEAKABLE CARD BACKGROUND VARIABLES
    // Adjust these to control card appearance in both light/dark modes
    // ============================================
    --card-surface-amount: 85%;      // How much base surface color (higher = more neutral)
    --card-tint-amount: 95%;         // How much accent color tint (higher = more colorful)
    --card-opacity: 25%;             // Overall opacity (lower = more page background shows through)

    @media (max-width: 1200px) {
      flex: 0 0 calc(50% - 0.75rem); // tablet: 2 cards, each exactly 1/2 minus gap
      width: calc(50% - 0.75rem);
      max-width: calc(50% - 0.75rem);
    }

    @media (max-width: 768px) {
      flex: 0 0 var(--card-width); // mobile: use JavaScript calculated width
      width: var(--card-width);
      max-width: var(--card-width);
    }


    :deep(.p-card-body) {
      padding: 0rem;
      height: 100%;
      display: flex;
      flex-direction: column;
    }



    &.data-science-card {
      background: linear-gradient(135deg,
        color-mix(in srgb,
          color-mix(in srgb, var(--p-surface-b) var(--card-surface-amount), var(--p-blue-500) var(--card-tint-amount))
          var(--card-opacity), transparent) 0%,
        color-mix(in srgb,
          color-mix(in srgb, var(--p-surface-c) var(--card-surface-amount), var(--p-blue-600) var(--card-tint-amount))
          var(--card-opacity), transparent) 100%);
    }

    &.weather-card {
      background: linear-gradient(135deg,
        color-mix(in srgb,
          color-mix(in srgb, var(--p-surface-b) var(--card-surface-amount), var(--p-purple-500) var(--card-tint-amount))
          var(--card-opacity), transparent) 0%,
        color-mix(in srgb,
          color-mix(in srgb, var(--p-surface-c) var(--card-surface-amount), var(--p-purple-600) var(--card-tint-amount))
          var(--card-opacity), transparent) 100%);
    }

    &.biomedical-card {
      background: linear-gradient(135deg,
        color-mix(in srgb,
          color-mix(in srgb, var(--p-surface-b) var(--card-surface-amount), var(--p-green-500) var(--card-tint-amount))
          var(--card-opacity), transparent) 0%,
        color-mix(in srgb,
          color-mix(in srgb, var(--p-surface-c) var(--card-surface-amount), var(--p-green-600) var(--card-tint-amount))
          var(--card-opacity), transparent) 100%);
    }

    &.wildfire-card {
      background: linear-gradient(135deg,
        color-mix(in srgb,
          color-mix(in srgb, var(--p-surface-b) var(--card-surface-amount), var(--p-orange-500) var(--card-tint-amount))
          var(--card-opacity), transparent) 0%,
        color-mix(in srgb,
          color-mix(in srgb, var(--p-surface-c) var(--card-surface-amount), var(--p-orange-600) var(--card-tint-amount))
          var(--card-opacity), transparent) 100%);
    }

    &.geospatial-card {
      background: linear-gradient(135deg,
        color-mix(in srgb,
          color-mix(in srgb, var(--p-surface-b) var(--card-surface-amount), var(--p-amber-500) var(--card-tint-amount))
          var(--card-opacity), transparent) 0%,
        color-mix(in srgb,
          color-mix(in srgb, var(--p-surface-c) var(--card-surface-amount), var(--p-amber-600) var(--card-tint-amount))
          var(--card-opacity), transparent) 100%);

      .domain-content {
        .domain-description {
          line-height: 1.4;
          margin-bottom: 0rem;
        }

        .use-case-highlight {
          margin-bottom: 0.75rem;
          padding: 0.75rem;
          line-height: 1.4;
        }
      }
    }

    &.custom-domain-card {
      background: linear-gradient(135deg,
        color-mix(in srgb,
          color-mix(in srgb, var(--p-surface-b) var(--card-surface-amount), var(--p-indigo-500) var(--card-tint-amount))
          var(--card-opacity), transparent) 0%,
        color-mix(in srgb,
          color-mix(in srgb, var(--p-surface-c) var(--card-surface-amount), var(--p-blue-500) var(--card-tint-amount))
          var(--card-opacity), transparent) 100%);
      border: 2px dashed rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.3);
      position: relative;

      &::after {
        content: '';
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 80%;
        height: 80%;
        border: 1px dashed rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.2);
        border-radius: 0.5rem;
        pointer-events: none;
      }
    }

    .domain-content {
      padding: 1.25rem;
      transition: all 0.4s ease;
      position: relative;
      z-index: 1;
      height: 100%;
      display: flex;
      flex-direction: column;
      min-height: 100%;
      background: transparent;

      .domain-icon {
        width: 3rem;
        height: 3rem;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 1rem;
        transition: all 0.3s ease;

        &.data-science {
          background: linear-gradient(135deg, var(--p-slate-800), var(--p-slate-600));
          color: var(--p-slate-200);
        }

        &.weather {
          background: linear-gradient(135deg, var(--p-indigo-800), var(--p-indigo-500));
          color: var(--p-indigo-100);
        }

        &.biomedical {
          background: linear-gradient(135deg, var(--p-green-900), var(--p-green-600));
          color: var(--p-green-100);
        }

        &.wildfire {
          background: linear-gradient(135deg, var(--p-orange-700), var(--p-orange-600));
          color: var(--p-orange-200);
        }

        &.geospatial {
          background: linear-gradient(135deg, var(--p-amber-700), var(--p-amber-500));
          color: var(--p-amber-100);
        }

        &.custom-domain {
          background: linear-gradient(135deg, var(--p-primary-color), var(--p-blue-500));
          color: var(--p-surface-0);
          border: 2px dashed color-mix(in srgb, var(--p-surface-0) 40%, transparent);
          animation: pulse-glow 2s infinite;

          @keyframes pulse-glow {
            0%, 100% {
              box-shadow: 0 0 8px rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.4);
            }
            50% {
              box-shadow: 0 0 16px rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.6);
            }
          }
        }

        :deep(svg) {
          width: 3rem;
          height: 3rem;
          fill: currentColor;
        }
      }

      .domain-title {
        font-size: 1.25rem;
        font-weight: 600;
        margin-bottom: 1rem;
        text-align: center;
        transition: color 0.3s ease;
        color: var(--p-text-color);
      }

      .domain-description {
        color: var(--p-text-muted-color);
        line-height: 1.6;
        margin-bottom: 1.5rem;
        text-align: center;
        font-size: 0.95rem;
        transition: color 0.3s ease;
      }

      .domain-tools {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        justify-content: center;
        margin-bottom: 1.5rem;
      }

      .use-case-highlight {
        background: var(--p-surface-b);
        border: 1px solid var(--p-surface-border);
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0.5rem;
        font-size: 0.875rem;
        line-height: 1.5;
        color: var(--p-text-color);
        text-align: left;

        strong {
          color: var(--p-primary-color);
          font-weight: 600;
        }
      }
    }
  }
}
</style>
