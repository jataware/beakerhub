<template>
      <main class="dashboard-main">

        <section class="domain-selection">
          <h2 class="section-title">Create New Session</h2>
          <p class="section-subtitle">
            Choose a domain to create a new session
          </p>

          <div v-if="contextsLoading" class="loading-state">
            <i class="pi pi-spin pi-spinner"></i>
            <p>Loading contexts...</p>
          </div>

          <div v-else-if="contextsError" class="error-state">
            <i class="pi pi-exclamation-triangle"></i>
            <p>{{ contextsError }}</p>
            <Button @click="fetchContexts" size="small">Retry</Button>
          </div>

          <div v-else class="domain-cards">
            <Card
              v-for="context in dynamicContexts"
              :key="context.slug"
              :class="['domain-card', getContextCardClass(context), { expanded: expandedCard === context.slug }]"
              @click.stop="showDomainDetails(context.slug)"
            >
              <template #header>
                <div class="card-header">
                  <div :class="['domain-icon', getContextTheme(context)]">
                    <component :is="getContextIconComponent(context)" />
                  </div>
                  <div class="card-header-content">
                    <h3 class="domain-title">{{ context.display_name }}</h3>
                    <p class="domain-description">
                      {{ getFirstSentence(context.description) }}
                    </p>
                  </div>
                </div>
              </template>
              <template #content>
                <div class="domain-summary">
                  <template v-if="getDisplayItems(context).emptyMessage">
                    <div class="summary-item">
                      <span class="empty-state">{{ getDisplayItems(context).emptyMessage }}</span>
                    </div>
                  </template>

                  <template v-else>
                    <div class="summary-item" v-if="getDisplayItems(context).workflows.length > 0 || getDisplayItems(context).noWorkflowsMessage">
                      <span class="summary-label">Workflows:</span>
                      <div class="summary-tags" v-if="getDisplayItems(context).workflows.length > 0">
                        <Tag
                          v-for="(workflow, idx) in getDisplayItems(context).workflows"
                          :key="idx"
                          :value="workflow.title"
                          size="small"
                        />
                        <Tag
                          v-if="getDisplayItems(context).workflowsMore > 0"
                          :value="`+${getDisplayItems(context).workflowsMore} more`"
                          size="small"
                          severity="secondary"
                        />
                      </div>
                      <span v-else-if="getDisplayItems(context).noWorkflowsMessage" class="empty-state">{{ getDisplayItems(context).noWorkflowsMessage }}</span>
                    </div>

                    <div class="summary-item" v-if="getDisplayItems(context).integrations.length > 0 || getDisplayItems(context).noIntegrationsMessage">
                      <span class="summary-label">Integrations:</span>
                      <div class="summary-tags" v-if="getDisplayItems(context).integrations.length > 0">
                        <Tag
                          v-for="(integration, idx) in getDisplayItems(context).integrations"
                          :key="idx"
                          :value="typeof integration === 'string' ? integration : integration.name || 'Integration'"
                          size="small"
                        />
                        <Tag
                          v-if="getDisplayItems(context).integrationsMore > 0"
                          :value="`+${getDisplayItems(context).integrationsMore} more`"
                          size="small"
                          severity="secondary"
                        />
                      </div>
                      <span v-else-if="getDisplayItems(context).noIntegrationsMessage" class="empty-state">{{ getDisplayItems(context).noIntegrationsMessage }}</span>
                    </div>
                  </template>
                </div>
                <Button
                  class="play-button"
                  rounded
                  raised
                  size="large"
                  severity="success"
                  title="Launch session"
                  aria-label="Launch session"
                  icon="pi pi-play-circle"
                  @click.stop="createEnvironment(context.slug)"
                />
              </template>
            </Card>
          </div>
        </section>

        <section class="your-sessions">
          <h2 class="section-title">Your Sessions</h2>
          <DataTable :value="sessionsList" tableStyle="min-width: 50rem">
            <template #empty>No active sessions.</template>
            <Column header="Session ID">
              <template #body="slotProps">
                {{ getContextName(slotProps.data.name) }}
              </template>
            </Column>
            <Column header="Context">
              <template #body="slotProps">
                {{ getContextName(slotProps.data.user_options?.contextSlug) }}
              </template>
            </Column>
            <Column header="Status">
              <template #body="slotProps">
                <Tag :severity="getStatusSeverity(slotProps.data)" :value="getStatusLabel(slotProps.data)" />
              </template>
            </Column>
            <Column header="Last Activity">
              <template #body="slotProps">
                {{ formatLastActivity(slotProps.data.last_activity) }}
              </template>
            </Column>
            <Column header="Actions">
              <template #body="slotProps">
                <div class="session-actions">
                  <Button label="Reconnect" size="small" @click="reconnectSession(slotProps.data)" />
                  <Button label="Delete" size="small" severity="danger" @click="confirmDeleteSession(slotProps.data)" />
                </div>
              </template>
            </Column>
            <Column class="refresh" style="padding: 0; width: min-content;">
              <template #header><Button @click="refreshSessions">⟳</Button></template>
            </Column>
          </DataTable>
        </section>
      </main>

    <Dialog
      v-model:visible="detailsDialogVisible"
      modal
      header="Domain Details"
      :style="{ width: '900px', maxWidth: '90vw' }"
    >
      <div v-if="selectedDomainDetails" class="domain-details-dialog">
        <div class="dialog-header">
          <h3>{{ selectedDomainDetails.title }}</h3>
          <p>{{ selectedDomainDetails.description }}</p>
        </div>

        <div class="detail-sections">
          <div class="detail-section" v-if="selectedDomainDetails.workflows && selectedDomainDetails.workflows.length > 0">
            <h4>Workflows</h4>
            <div class="tags">
              <Tag
                v-for="workflow in selectedDomainDetails.workflows"
                :key="workflow"
                :value="workflow"
                size="small"
              />
            </div>
          </div>

          <div class="detail-section" v-if="selectedDomainDetails.integrations && selectedDomainDetails.integrations.length > 0">
            <h4>Integrations</h4>
            <div class="tags">
              <Tag
                v-for="integration in selectedDomainDetails.integrations"
                :key="integration"
                :value="integration"
                size="small"
              />
            </div>
          </div>
        </div>

        <div class="dialog-actions">
          <Button @click="detailsDialogVisible = false" text>Close</Button>
          <Button @click="createEnvironment(selectedDomainDetails.slug); detailsDialogVisible = false">
            Launch Notebook
          </Button>
        </div>
      </div>
    </Dialog>

    <Dialog
      v-model:visible="creationDialogVisible"
      modal
      :style="{ width: '400px' }"
      :closable="false"
    >
      <div class="creation-dialog">
        <div class="loading-spinner">
          <i class="pi pi-spin pi-spinner"></i>
        </div>
        <div class="loading-text">
          Starting your Notebook Session
        </div>
      </div>
    </Dialog>

    <ConfirmDialog />
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import Button from 'primevue/button';
import Card from 'primevue/card';
import Tag from 'primevue/tag';
import Dialog from 'primevue/dialog';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import ConfirmDialog from 'primevue/confirmdialog';
// import {} from 'primeicons/';
import { useConfirm } from 'primevue/useconfirm';
import DataScienceIcon from '@/components/icons/DataScienceIcon.vue';
import BiomedicalIcon from '@/components/icons/BiomedicalIcon.vue';
import WeatherIcon from '@/components/icons/WeatherIcon.vue';
import GeospatialIcon from '@/components/icons/GeospatialIcon.vue';
import WildfireIcon from '@/components/icons/WildfireIcon.vue';
import CustomDomainIcon from '@/components/icons/CustomDomainIcon.vue';
import { useContextStore, type Context, getVueIconComponent } from '@/stores/context';
import { useUserStore } from '@/stores/user';
import { useSessionStore } from '@/stores/session';

interface DomainDetailsView {
  title: string
  slug: string
  description: string
  workflows: string[]
  integrations: string[]
  tools: string[]
  languages: string[]
}

interface DisplayItems {
  workflows: Array<{ title: string }>
  integrations: Array<{ name: string } | string>
  workflowsMore: number
  integrationsMore: number
  emptyMessage?: string | null
  noWorkflowsMessage?: string
  noIntegrationsMessage?: string
}

const router = useRouter();
const expandedCard = ref<string | null>(null);
const detailsDialogVisible = ref(false);
const selectedDomainDetails = ref<DomainDetailsView | null>(null);

const creationDialogVisible = ref(false);

const userStore = useUserStore();
const contextStore = useContextStore();
const sessionStore = useSessionStore();
const confirm = useConfirm();

// Map of Vue icon component names to actual components
const iconComponents: Record<string, any> = {
  DataScienceIcon,
  BiomedicalIcon,
  WeatherIcon,
  GeospatialIcon,
  WildfireIcon,
  CustomDomainIcon,
};

// Use store state for contexts
const contextsLoading = computed(() => contextStore.contextsLoading);
const contextsError = computed(() => contextStore.contextsError);
const dynamicContexts = computed(() => contextStore.sortedEnabledContexts);

function showDomainDetails(contextSlug: string) {
  const context = dynamicContexts.value.find(c => c.slug === contextSlug);

  if (!context) {
    console.error('context not found:', contextSlug);
    return;
  }

  // use data from the /contexts/detail fetch we already did
  selectedDomainDetails.value = {
    title: context.display_name,
    slug: context.slug,
    description: context.description,
    workflows: context.workflows.map(w => w.title),
    integrations: context.integrations.map(i => i.name).slice(0, 10),
    tools: [],
    languages: []
  };
  detailsDialogVisible.value = true;
}

const refreshSessions = () => {
  sessionStore.refresh();
}

async function createEnvironment(contextSlug) {
  router.push({name: "launch", params: {"context": contextSlug}})
}

function getContextCardClass(context: Context): string {
  // Use theme from context if available, otherwise infer from slug
  const theme = context.theme?.toLowerCase() || '';
  if (theme === 'biomedical') return 'biomedical-card';
  if (theme === 'weather') return 'weather-card';
  if (theme === 'geospatial') return 'geospatial-card';
  if (theme === 'wildfire') return 'wildfire-card';
  if (theme === 'data-science') return 'data-science-card';

  // Fallback: infer from slug for backwards compatibility
  const lowerSlug = context.slug.toLowerCase();
  if (lowerSlug.includes('bio') || lowerSlug.includes('medical')) {
    return 'biomedical-card';
  } else if (lowerSlug.includes('weather') || lowerSlug.includes('aviation') || lowerSlug.includes('space')) {
    return 'weather-card';
  }
  return 'data-science-card';
}

function getContextTheme(context: Context): string {
  // Use theme from context if available, otherwise infer from slug
  const theme = context.theme?.toLowerCase() || '';
  if (theme) return theme;

  // Fallback: infer from slug for backwards compatibility
  const lowerSlug = context.slug.toLowerCase();
  if (lowerSlug.includes('bio') || lowerSlug.includes('medical')) {
    return 'biomedical';
  } else if (lowerSlug.includes('weather') || lowerSlug.includes('aviation') || lowerSlug.includes('space')) {
    return 'weather';
  }
  return 'data-science';
}

function getContextIconComponent(context: Context): any {
  // Use icon from context if available (vue:// scheme)
  const iconName = getVueIconComponent(context.icon);
  if (iconName && iconComponents[iconName]) {
    return iconComponents[iconName];
  }

  // Fallback: infer from theme
  const theme = getContextTheme(context);
  switch (theme) {
    case 'biomedical': return BiomedicalIcon;
    case 'weather': return WeatherIcon;
    case 'geospatial': return GeospatialIcon;
    case 'wildfire': return WildfireIcon;
    default: return DataScienceIcon;
  }
}

function getFirstSentence(text: string): string {
  if (!text) return "";
  // match first sentence ending with . ! or ?
  const match = text.match(/^[^.!?]+[.!?]/);
  return match ? match[0].trim() : text;
}

function shuffleArray<T>(array: T[]): T[] {
  const shuffled = [...array];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
}

// Memoized display items that only recalculate when dynamicContexts changes
const displayItemsCache = computed<Map<string, DisplayItems>>(() => {
  const cache = new Map<string, DisplayItems>();

  dynamicContexts.value.forEach(context => {
    const workflows = context.workflows || [];
    const integrations = context.integrations || [];

    const hasWorkflows = workflows.length > 0;
    const hasIntegrations = integrations.length > 0;

    const shuffledWorkflows = shuffleArray(workflows);
    const shuffledIntegrations = shuffleArray(integrations);

    let displayItems: DisplayItems;

    if (!hasWorkflows && !hasIntegrations) {
      displayItems = {
        workflows: [],
        integrations: [],
        workflowsMore: 0,
        integrationsMore: 0,
        emptyMessage: "Default. No workflows or integrations."
      };
    } else if (hasWorkflows && hasIntegrations) {
      const displayWorkflows = shuffledWorkflows.slice(0, 2);
      const displayIntegrations = shuffledIntegrations.slice(0, 2);
      displayItems = {
        workflows: displayWorkflows,
        integrations: displayIntegrations,
        workflowsMore: Math.max(0, workflows.length - 2),
        integrationsMore: Math.max(0, integrations.length - 2),
        emptyMessage: null
      };
    } else if (hasWorkflows && !hasIntegrations) {
      const displayWorkflows = shuffledWorkflows.slice(0, 5);
      displayItems = {
        workflows: displayWorkflows,
        integrations: [],
        workflowsMore: Math.max(0, workflows.length - 5),
        integrationsMore: 0,
        noIntegrationsMessage: "Context doesn't have integrations."
      };
    } else {
      const displayIntegrations = shuffledIntegrations.slice(0, 5);
      displayItems = {
        workflows: [],
        integrations: displayIntegrations,
        workflowsMore: 0,
        integrationsMore: Math.max(0, integrations.length - 5),
        noWorkflowsMessage: "Context doesn't have workflows."
      };
    }

    cache.set(context.slug, displayItems);
  });

  return cache;
});

function getDisplayItems(context: Context): DisplayItems {
  return displayItemsCache.value.get(context.slug) || {
    workflows: [],
    integrations: [],
    workflowsMore: 0,
    integrationsMore: 0,
    emptyMessage: "Context doesn't have workflows or integrations."
  };
}

async function fetchContexts() {
  try {
    await contextStore.ensureContextsLoaded();
  } catch (error) {
    console.error('Failed to fetch contexts:', error);
  }
}

// Session list computed property
interface SessionListItem {
  name: string;
  ready: boolean;
  stopped: boolean;
  pending: "spawn" | "stop" | null;
  url: string;
  full_url?: string;
  last_activity: string;
  user_options: { context?: string } | null;
}

const sessionsList = computed<SessionListItem[]>(() => {
  if (!sessionStore.servers) return [];
  return Object.entries(sessionStore.servers).map(([name, data]) => ({
    name,
    ...data
  }));
});

function getContextName(slug: string | undefined): string {
  if (!slug) return 'Unknown';
  const context = contextStore.contexts?.find(c => c.slug === slug);
  return context?.display_name ?? slug;
}

function getStatusSeverity(session: SessionListItem): "success" | "warn" | "info" | "secondary" | undefined {
  if (session.stopped) return 'warn';
  if (session.pending) return 'info';
  if (session.ready) return 'success';
  return 'secondary';
}

function getStatusLabel(session: SessionListItem): string {
  if (session.stopped) return 'Stopped';
  if (session.pending === 'spawn') return 'Starting...';
  if (session.pending === 'stop') return 'Shutting Down...';
  if (session.ready) return 'Running';
  return 'Unknown';
}

function formatLastActivity(dateStr: string): string {
  if (!dateStr) return 'Unknown';
  const date = new Date(dateStr);
  return date.toLocaleString();
}

function reconnectSession(session: SessionListItem) {
  router.push({name: "session", params: {session: session.name}})
}

function confirmDeleteSession(session: SessionListItem) {
  confirm.require({
    message: 'Are you sure you want to delete this session?',
    header: 'Delete Session',
    acceptClass: 'p-button-danger',
    accept: () => sessionStore.deleteServer(session.name)
  });
}

onMounted(async () => {
  await contextStore.ensureContextsLoaded();
});

</script>

<style lang="scss" scoped>
.dashboard-page {
  min-height: 100vh;
  background: linear-gradient(135deg,
    var(--p-surface-a) 0%,
    rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.03) 25%,
    rgba(var(--p-blue-500-rgb, 59, 130, 246), 0.02) 50%,
    rgba(var(--p-purple-500-rgb, 168, 85, 247), 0.03) 75%,
    var(--p-surface-a) 100%
  );
  color: var(--p-text-color);
  position: relative;


  &::before {
    content: '';
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: radial-gradient(
      circle at 20% 20%,
      rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.05) 0%,
      transparent 50%
    ),
    radial-gradient(
      circle at 80% 80%,
      rgba(var(--p-blue-500-rgb, 59, 130, 246), 0.04) 0%,
      transparent 50%
    ),
    radial-gradient(
      circle at 40% 60%,
      rgba(var(--p-purple-500-rgb, 168, 85, 247), 0.03) 0%,
      transparent 50%
    );
    pointer-events: none;
    z-index: 0;
  }

  > * {
    position: relative;
    z-index: 1;
  }

  // defensive styles to prevent external interference
  * {
    box-sizing: border-box;
  }
  button, input, select, textarea {
    font-family: inherit;
    font-size: inherit;
  }
}

.dashboard-container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 2rem;
}

header.dashboard-header {
  padding: 2rem 0;
  background: transparent;
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.1);
  position: relative;
  z-index: 10;
  display: block;


  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .header-actions {
      display: flex;
      gap: 1rem;
      align-items: center;

      button {
        backdrop-filter: blur(8px);
        border: 1px solid rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.2);
        transition: all 0.3s ease;

        &:hover {
          background: rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.1);
          border-color: var(--p-primary-color);
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.3);
        }
      }

      .profile-menu {
        position: relative;

        .profile-dropdown {
          position: absolute;
          top: calc(100% + 8px);
          right: 0;
          background: var(--p-surface-b);
          background-color: var(--p-surface-b);
          border: 1px solid var(--p-surface-border);
          border-radius: 8px;
          box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
          backdrop-filter: blur(10px);
          min-width: 160px;
          z-index: 1100;
          overflow: hidden;

          .profile-menu-item {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.75rem 1rem;
            color: var(--p-text-color);
            cursor: pointer;
            transition: all 0.2s ease;
            font-size: 0.875rem;

            &:hover {
              background: rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.1);
              color: var(--p-primary-color);
            }

            &:not(:last-child) {
              border-bottom: 1px solid var(--p-surface-border);
            }

            i {
              font-size: 1rem;
              opacity: 0.7;
            }

            span {
              font-weight: 500;
            }

            &.user-email-item {
              cursor: default;
              background: var(--p-surface-c);

              &:hover {
                background: var(--p-surface-c);
                color: var(--p-text-color);
              }

              .user-email {
                color: var(--p-text-secondary-color);
                font-weight: 400;
                font-size: 0.8125rem;
              }
            }
          }
        }
      }
    }
  }
}

.dashboard-main {
  padding: 3rem 0;
  display: flex;
  flex-direction: column;
  gap: 0;
  background: transparent !important;
  padding-left: 25%;
  padding-right: 25%;
}

.section-title {
  font-size: 2rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
  background: linear-gradient(135deg, var(--p-text-color) 0%, rgba(var(--p-primary-color-rgb, 99, 102, 241), 0.8) 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.section-subtitle {
  font-size: 1.125rem;
  color: var(--text-color-secondary);
  margin-bottom: 3rem;
  opacity: 0.8;
}


.your-sessions {
  margin-bottom: 4rem;

  .section-title {
    margin-bottom: 1.5rem;
  }

  .session-actions {
    display: flex;
    gap: 0.5rem;
  }

  .refresh {
    background-color: orchid;
  }
}

.domain-selection {
  margin-bottom: 4rem;

  .loading-state,
  .error-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem 2rem;
    gap: 1rem;

    i {
      font-size: 3rem;
      color: var(--p-primary-color);
    }

    p {
      font-size: 1.125rem;
      color: var(--text-color-secondary);
      margin: 0;
    }
  }

  .error-state i {
    color: var(--p-red-500);
  }

  .domain-cards {
    cursor: pointer;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
    gap: 2rem;

    .domain-card {
      transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
      background: var(--p-surface-b);
      backdrop-filter: blur(10px);
      border: 1px solid var(--p-surface-border);
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
      overflow: hidden;
      position: relative;

      // ============================================
      // TWEAKABLE CARD BACKGROUND VARIABLES
      // Adjust these to control card appearance in both light/dark modes
      // ============================================
      --card-surface-amount: 85%;      // How much base surface color (higher = more neutral)
      --card-tint-amount: 25%;         // How much accent color tint (higher = more colorful)
      --card-opacity: 90%;             // Overall opacity (lower = more page background shows through)

      &::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(135deg, transparent 0%, color-mix(in srgb, var(--p-surface-a) 10%, transparent) 100%);
        opacity: 0;
        transition: opacity 0.3s ease;
        z-index: 0;
      }

      &:hover {
        transform: translateY(-8px) scale(1.02);
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);

        &::before {
          opacity: 1;
        }
      }

      &.data-science-card {
        background: linear-gradient(135deg,
          color-mix(in srgb,
            color-mix(in srgb, var(--p-surface-b) var(--card-surface-amount), var(--p-blue-500) var(--card-tint-amount))
            var(--card-opacity), transparent) 0%,
          color-mix(in srgb,
            color-mix(in srgb, var(--p-surface-c) var(--card-surface-amount), var(--p-blue-600) var(--card-tint-amount))
            var(--card-opacity), transparent) 100%);

        .card-header {
          background: transparent;
        }

        &:hover .card-header {
          background: linear-gradient(135deg,
            var(--p-slate-800) 0%,
            var(--p-slate-700) 25%,
            var(--p-slate-600) 50%,
            var(--p-slate-500) 75%,
            var(--p-slate-400) 100%
          );
          background-size: 200% 200%;
          animation: shimmer 0.75s ease-in-out 1;
          animation-fill-mode: forwards;
          color: var(--p-surface-0);

          .domain-title, .domain-description {
            color: var(--p-surface-0);
            text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
          }

          .domain-icon {
            background: linear-gradient(135deg, var(--p-surface-0) 0%, var(--p-slate-50) 100%);
            color: var(--p-slate-800);
            box-shadow: 0 4px 12px color-mix(in srgb, var(--p-surface-0) 30%, transparent);
          }

          .card-actions button:not(.p-button-text) {
            background: linear-gradient(135deg, var(--p-surface-0) 0%, var(--p-slate-50) 100%);
            color: var(--p-slate-800);
            border: 1px solid color-mix(in srgb, var(--p-surface-0) 30%, transparent);
            box-shadow: 0 4px 12px color-mix(in srgb, var(--p-surface-0) 20%, transparent);
          }
        }
      }

      &.biomedical-card {
        background: linear-gradient(135deg,
          color-mix(in srgb, var(--p-surface-b) 90%, var(--p-green-500) 10%) 0%,
          color-mix(in srgb, var(--p-surface-c) 85%, var(--p-green-600) 15%) 100%);

        .card-header {
          background: transparent;
        }

        &:hover .card-header {
          background: linear-gradient(135deg,
            var(--p-green-900) 0%,
            var(--p-green-800) 25%,
            var(--p-green-700) 50%,
            var(--p-green-600) 75%,
            var(--p-green-500) 100%
          );
          background-size: 200% 200%;
          animation: shimmer 0.75s ease-in-out 1;
          animation-fill-mode: forwards;
          color: var(--p-surface-0);

          .domain-title, .domain-description {
            color: var(--p-surface-0);
            text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
          }

          .domain-icon {
            background: linear-gradient(135deg, var(--p-surface-0) 0%, var(--p-green-50) 100%);
            color: var(--p-green-900);
            box-shadow: 0 4px 12px color-mix(in srgb, var(--p-surface-0) 30%, transparent);
          }

          .card-actions button:not(.p-button-text) {
            background: linear-gradient(135deg, var(--p-surface-0) 0%, var(--p-green-50) 100%);
            color: var(--p-green-900);
            border: 1px solid color-mix(in srgb, var(--p-surface-0) 30%, transparent);
            box-shadow: 0 4px 12px color-mix(in srgb, var(--p-surface-0) 20%, transparent);
          }
        }
      }

      &.weather-card {
        background: linear-gradient(135deg,
          color-mix(in srgb, var(--p-surface-b) 90%, var(--p-purple-500) 10%) 0%,
          color-mix(in srgb, var(--p-surface-c) 85%, var(--p-purple-600) 15%) 100%);

        .card-header {
          background: transparent;
        }

        &:hover .card-header {
          background: linear-gradient(135deg,
            var(--p-indigo-800) 0%,
            var(--p-indigo-700) 25%,
            var(--p-indigo-600) 50%,
            var(--p-indigo-500) 75%,
            var(--p-violet-500) 100%
          );
          background-size: 200% 200%;
          animation: shimmer 0.75s ease-in-out 1;
          animation-fill-mode: forwards;
          color: var(--p-surface-0);

          .domain-title, .domain-description {
            color: var(--p-surface-0);
            text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
          }

          .domain-icon {
            background: linear-gradient(135deg, var(--p-surface-0) 0%, var(--p-purple-50) 100%);
            color: var(--p-indigo-800);
            box-shadow: 0 4px 12px color-mix(in srgb, var(--p-surface-0) 30%, transparent);
          }

          .card-actions button:not(.p-button-text) {
            background: linear-gradient(135deg, var(--p-surface-0) 0%, var(--p-purple-50) 100%);
            color: var(--p-indigo-800);
            border: 1px solid color-mix(in srgb, var(--p-surface-0) 30%, transparent);
            box-shadow: 0 4px 12px color-mix(in srgb, var(--p-surface-0) 20%, transparent);
          }
        }
      }

      .card-header {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 1.25rem;
        transition: all 0.4s ease;
        position: relative;
        z-index: 1;

        .domain-icon {
          width: 3rem;
          height: 3rem;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1.25rem;
          flex-shrink: 0;

          &.data-science {
            background: linear-gradient(135deg, var(--p-slate-800), var(--p-slate-600));
            color: var(--p-slate-200);
          }

          &.biomedical {
            background: linear-gradient(135deg, var(--p-green-900), var(--p-green-600));
            color: var(--p-green-100);
          }

          &.weather {
            background: linear-gradient(135deg, var(--p-indigo-800), var(--p-indigo-500));
            color: var(--p-indigo-100);
          }
        }

        .card-header-content {
          flex: 1;

          .domain-title {
            font-size: 1.25rem;
            font-weight: 600;
            margin: 0 0 0.5rem 0;
            color: var(--p-text-color);
          }

          .domain-description {
            color: var(--p-text-muted-color);
            font-size: 0.875rem;
            line-height: 1.4;
            margin: 0;
          }
        }

        .card-actions {
          display: flex;
          gap: 0.5rem;
          align-items: center;
        }
      }

      .domain-summary {
        .summary-item {
          display: flex;
          align-items: flex-start;
          gap: 1rem;
          margin-bottom: 1rem;

          .summary-label {
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--p-text-color);
            min-width: 80px;
            padding-top: 0.25rem;
          }

          .summary-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
          }

          .empty-state {
            font-size: 0.875rem;
            color: var(--text-color-secondary);
            font-style: italic;
            padding-top: 0.25rem;
          }
        }
      }

      .play-button {
        position: absolute;
        bottom: 1rem;
        right: 1rem;
        z-index: 1;
        width: 2.5rem;
        height: 2.5rem;
        opacity: 0.7;
        transition: opacity 0.2s ease, transform 0.2s ease;

        &:hover {
          opacity: 1;
          transform: scale(1.1);
        }
      }
    }
  }
}

@keyframes shimmer {
  0% {
    background-position: 200% 0;
  }
}

.resume-sessions {
  .loading-state,
  .error-state,
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 4rem 2rem;
    gap: 1rem;

    i {
      font-size: 3rem;
      color: var(--p-primary-color);
    }

    p {
      font-size: 1.125rem;
      color: var(--text-color-secondary);
      margin: 0;
    }
  }

  .error-state i {
    color: var(--p-red-500);
  }

  .empty-state i {
    color: var(--text-color-secondary);
    opacity: 0.5;
  }

  .sessions-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;

    .session-row {
      display: flex;
      align-items: center;
      gap: 1.5rem;
      padding: 1.5rem;
      border-radius: 12px;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      position: relative;
      backdrop-filter: blur(10px);
      background: var(--p-surface-a);
      border: 1px solid var(--p-surface-border);

      &.session-data-science {
        background: linear-gradient(135deg, var(--p-slate-50) 0%, var(--p-slate-200) 100%);
        border: 1px solid color-mix(in srgb, var(--p-slate-800) 20%, transparent);
        color: var(--p-text-color);

        .session-title {
          color: var(--p-text-color);
          font-weight: 600;
        }

        .session-description, .session-date {
          color: var(--p-text-muted-color);
        }

        .session-actions button {
          color: var(--p-text-color);
          border-color: var(--p-surface-border);

          &:hover {
            background: var(--p-surface-b);
            border-color: var(--p-primary-color);
            color: var(--p-primary-color);
          }

          &.p-button-danger:hover {
            background: color-mix(in srgb, var(--p-red-500) 80%, transparent);
            border-color: var(--p-red-500);
            color: var(--p-surface-0);
          }
        }

        &:hover {
          transform: translateY(-4px);
          box-shadow: 0 16px 40px color-mix(in srgb, var(--p-slate-800) 40%, transparent);
        }
      }

      &.session-biomedical {
        background: linear-gradient(135deg, var(--p-green-50) 0%, var(--p-green-100) 100%);
        border: 1px solid color-mix(in srgb, var(--p-green-900) 20%, transparent);
        color: var(--p-text-color);

        .session-title {
          color: var(--p-text-color);
          font-weight: 600;
        }

        .session-description, .session-date {
          color: var(--p-text-muted-color);
        }

        .session-actions button {
          color: var(--p-text-color);
          border-color: var(--p-surface-border);

          &:hover {
            background: var(--p-surface-b);
            border-color: var(--p-primary-color);
            color: var(--p-primary-color);
          }

          &.p-button-danger:hover {
            background: color-mix(in srgb, var(--p-red-500) 80%, transparent);
            border-color: var(--p-red-500);
            color: var(--p-surface-0);
          }
        }

        &:hover {
          transform: translateY(-4px);
          box-shadow: 0 16px 40px color-mix(in srgb, var(--p-green-900) 40%, transparent);
        }
      }

      &.session-weather {
        background: linear-gradient(135deg, var(--p-purple-50) 0%, var(--p-purple-100) 100%);
        border: 1px solid color-mix(in srgb, var(--p-indigo-800) 20%, transparent);
        color: var(--p-text-color);

        .session-title {
          color: var(--p-text-color);
          font-weight: 600;
        }

        .session-description, .session-date {
          color: var(--p-text-muted-color);
        }

        .session-actions button {
          color: var(--p-text-color);
          border-color: var(--p-surface-border);

          &:hover {
            background: var(--p-surface-b);
            border-color: var(--p-primary-color);
            color: var(--p-primary-color);
          }

          &.p-button-danger:hover {
            background: color-mix(in srgb, var(--p-red-500) 80%, transparent);
            border-color: var(--p-red-500);
            color: var(--p-surface-0);
          }
        }

        &:hover {
          transform: translateY(-4px);
          box-shadow: 0 16px 40px color-mix(in srgb, var(--p-indigo-800) 40%, transparent);
        }
      }

      .session-preview {
        width: 15rem;
        height: 10rem;
        background: color-mix(in srgb, var(--p-surface-0) 20%, transparent);
        border: 2px solid color-mix(in srgb, var(--p-surface-0) 30%, transparent);
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        backdrop-filter: blur(8px);
        transition: all 0.3s ease;
        overflow: hidden;

        img {
          width: 100%;
          height: 100%;
          object-fit: cover;
          border-radius: 6px;
        }

        .preview-placeholder {
          text-align: center;

          i {
            font-size: 1.5rem;
            color: var(--p-text-color);
            transition: transform 0.3s ease;
          }
        }
      }

      &:hover .session-preview {
        transform: scale(1.05);
        background: color-mix(in srgb, var(--p-surface-0) 30%, transparent);
        border-color: color-mix(in srgb, var(--p-surface-0) 60%, transparent);

        .preview-placeholder i {
          transform: scale(1.1);
          color: var(--p-text-color);
        }
      }

      .session-info {
        flex: 1;
        min-width: 0;

        .session-title {
          font-size: 1rem;
          font-weight: 600;
          margin-bottom: 0.5rem;
          line-height: 1.4;
          color: var(--p-text-color);
        }

        .session-description {
          font-size: 0.875rem;
          line-height: 1.4;
          margin-bottom: 0.75rem;
          overflow: hidden;
          text-overflow: ellipsis;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
        }

        .session-meta {
          display: flex;
          align-items: center;
          gap: 1rem;

          .session-date {
            font-size: 0.75rem;
            color: var(--text-color-secondary);
          }
        }
      }

      .session-actions {
        display: flex;
        gap: 0.5rem;
        align-items: center;
        flex-shrink: 0;

        button {
          transition: all 0.2s ease;

          &:hover {
            background: var(--p-surface-c);
            transform: translateY(-1px);
          }

          &.p-button-secondary:hover {
            background: var(--p-surface-d);
            border-color: var(--p-primary-color);
            color: var(--p-primary-color);
          }

          &.p-button-danger:hover {
            background: color-mix(in srgb, var(--p-red-500) 10%, transparent);
            border-color: var(--p-red-500);
            color: var(--p-red-500);
          }
        }
      }
    }
  }
}

.domain-selection-dialog {
  .selection-header {
    margin-bottom: 2rem;

    .domain-info {
      display: flex;
      align-items: center;
      gap: 1rem;

      .domain-icon-large {
        width: 4rem;
        height: 4rem;
        min-width: 4rem;
        min-height: 4rem;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
        color: white;
        flex-shrink: 0;

        &.data-science {
          background: linear-gradient(135deg, var(--p-slate-800), var(--p-slate-600));
          color: var(--p-slate-200);
        }

        &.biomedical {
          background: linear-gradient(135deg, var(--p-green-900), var(--p-green-600));
          color: var(--p-green-100);
        }

        &.weather {
          background: linear-gradient(135deg, var(--p-indigo-800), var(--p-indigo-500));
          color: var(--p-indigo-100);
        }
      }

      h3 {
        font-size: 1.5rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
        color: var(--p-text-color);
      }

      p {
        color: var(--text-color-secondary);
        margin: 0;
      }
    }
  }

  .selection-options {
    .option-section {
      margin-bottom: 2rem;

      h4 {
        font-size: 1rem;
        font-weight: 600;
        color: var(--p-text-color);
        margin-bottom: 1rem;
      }

      .environment-name-input {
        width: 100%;
        padding: 0.75rem;
        border: 1px solid var(--p-surface-border);
        border-radius: 0.375rem;
        background: var(--p-surface-a);
        color: var(--p-text-color);
        font-size: 1rem;

        &:focus {
          outline: none;
          border-color: var(--p-primary-color);
          box-shadow: 0 0 0 2px rgba(var(--p-primary-color), 0.2);
        }
      }

      .template-options {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1rem;

        .template-option {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 1rem;
          border: 1px solid var(--p-surface-border);
          border-radius: 0.375rem;
          background: var(--p-surface-b);
          cursor: pointer;
          transition: all 0.2s ease;

          &:hover {
            background: var(--p-surface-c);
          }

          &.active {
            border-color: var(--p-primary-color);
            background: rgba(var(--p-primary-color), 0.1);
          }

          i {
            font-size: 1.25rem;
            color: var(--p-primary-color);
          }

          span {
            font-weight: 500;
            color: var(--p-text-color);
          }
        }
      }

      .quick-start-options {
        display: flex;
        flex-direction: column;
        gap: 1rem;

        .checkbox-option {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          cursor: pointer;

          input[type="checkbox"] {
            width: 1.25rem;
            height: 1.25rem;
            accent-color: var(--p-primary-color);
          }

          span {
            color: var(--p-text-color);
          }
        }
      }
    }
  }

  .dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: 1rem;
    margin-top: 2rem;
    padding-top: 2rem;
    border-top: 1px solid var(--p-surface-border);
  }
}

.creation-dialog {
  text-align: center;
  padding: 2rem 1rem;

  .loading-spinner {
    margin-bottom: 1.5rem;

    i {
      font-size: 3.5rem;
      color: var(--p-primary-color);
    }
  }

  .loading-text {
    font-size: 1.125rem;
    font-weight: 500;
    color: var(--p-text-color);
  }
}

.domain-details-dialog {
  .dialog-header {
    margin-bottom: 2rem;

    h3 {
      font-size: 1.5rem;
      font-weight: 600;
      margin-bottom: 1rem;
      color: var(--p-text-color);
    }

    p {
      color: var(--text-color-secondary);
      line-height: 1.6;
    }
  }

  .detail-sections {
    .detail-section {
      margin-bottom: 2rem;

      h4 {
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--p-text-color);
        margin-bottom: 1rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
      }

      .tags {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
      }

      .agent-description {
        color: var(--text-color-secondary);
        line-height: 1.6;
      }
    }
  }

  .dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: 1rem;
    margin-top: 2rem;
    padding-top: 2rem;
    border-top: 1px solid var(--p-surface-border);
  }
}

@media (max-width: 768px) {
  .dashboard-container {
    padding: 0 1rem;
  }

  .dashboard-header .header-content {
    flex-direction: column;
    gap: 1rem;
    text-align: center;
  }

  .domain-selection .domain-cards {
    grid-template-columns: 1fr;
  }

  .resume-sessions .sessions-list .session-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 1rem;

    .session-preview {
      width: 100%;
      height: 120px;
    }

    .session-actions {
      width: 100%;
      justify-content: flex-start;
    }
  }
}

.dashboard-footer {

  // .footer-content {
  //   max-width: 1400px;
  //   margin: 0 auto;
  //   padding: 4rem 2rem 2rem;
  //   display: grid;
  //   grid-template-columns: 2fr 1fr 1fr 1fr;
  //   gap: 2rem;

  //   .footer-section {
  //     .footer-brand {
  //       display: flex;
  //       align-items: center;
  //       gap: 0.5rem;
  //       margin-bottom: 1rem;

  //       h3 {
  //         font-size: 1.25rem;
  //         font-weight: 600;
  //         color: var(--p-primary-color);
  //         margin: 0;
  //       }
  //     }

  //     .footer-description {
  //       color: var(--text-color-secondary);
  //       line-height: 1.6;
  //     }

  //     .footer-title {
  //       font-size: 1rem;
  //       font-weight: 600;
  //       margin-bottom: 1rem;
  //       color: var(--p-text-color);
  //     }

  //     .footer-links {
  //       list-style: none;
  //       padding: 0;
  //       margin: 0;

  //       li {
  //         margin-bottom: 0.5rem;

  //         a {
  //           color: var(--text-color-secondary);
  //           text-decoration: none;
  //           transition: color 0.2s;

  //           &:hover {
  //             color: var(--p-primary-color);
  //           }
  //         }
  //       }
  //     }
  //   }
  // }

  // .footer-bottom {
  //   max-width: 1400px;
  //   margin: 0 auto;
  //   padding: 2rem;
  //   text-align: center;
  //   color: var(--text-color-secondary);
  // }
}

// @media (max-width: 768px) {
//   .dashboard-footer .footer-content {
//     grid-template-columns: 1fr !important;
//     gap: 2rem;
//   }
// }



</style>
