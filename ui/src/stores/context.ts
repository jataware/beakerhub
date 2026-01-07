import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { fetch } from '@/utils/fetch';

const API_BASE_URL = window.location.origin;

// ============================================
// Base/Reference Types
// ============================================

export interface Language {
  slug: string;
  subkernel: string;
  display_name?: string;
}

export interface ApiKey {
  id: number;
  env_var: string;
  display_name: string;
  description?: string;
}

export interface ApiKeyRequirement {
  env_var: string;
  display_name: string;
  required: boolean;
}

export interface WorkflowCategory {
  slug: string;
  display_name: string;
  description?: string;
  sort_order: number;
}

// ============================================
// Integration Types
// ============================================

export interface Integration {
  id: number;
  slug: string;
  name: string;
  description: string;
  enabled: boolean;
  source_package?: string;
  source_uuid?: string;
}

// Lightweight version for listings
export interface IntegrationSummary {
  slug: string;
  name: string;
  description: string;
}

// ============================================
// Workflow Types
// ============================================

export interface WorkflowStage {
  id: number;
  name: string;
  sort_order: number;
  description: string[];
  metadata: Record<string, unknown>;
}

export interface Workflow {
  id: number;
  title: string;
  human_description: string;
  agent_description: string;
  example_prompt: string;
  category: WorkflowCategory | null;
  hidden: boolean;
  enabled: boolean;
  is_context_default: boolean;  // from junction table (per-context setting)
  stages: WorkflowStage[];
  metadata: Record<string, unknown>;
  source_package?: string;
  source_path?: string;
}

// Lightweight version for listings (no stages)
export interface WorkflowSummary {
  id: number;
  title: string;
  human_description: string;
  example_prompt: string;
  category: WorkflowCategory | null;
  hidden: boolean;
  enabled: boolean;
  is_context_default: boolean;
  stage_count: number;
}

// ============================================
// Context Types
// ============================================

export interface Context {
  id: number;
  slug: string;
  display_name: string;
  description: string;
  icon: string;                    // URL or vue:// scheme
  theme: string;
  image?: string;
  image_enabled?: boolean | null;
  weight: number;
  enabled: boolean;
  default_payload: Record<string, unknown> | string;
  source_package?: string;
  source_key?: string;
  version?: string;
  visible_to_roles: string[];      // Empty = visible to all

  // Related entities
  languages: Language[];
  integrations: Integration[];
  workflows: Workflow[];
  api_keys: ApiKeyRequirement[];
}

// Lightweight version for dashboard listing
export interface ContextSummary {
  slug: string;
  display_name: string;
  description: string;
  icon: string;
  theme: string;
  weight: number;
  enabled: boolean;
  image_enabled: boolean | null;
  integration_count: number;
  workflow_count: number;
  integration_names: string[];
  workflow_titles: string[];
  visible_to_roles: string[];
}

// Full context detail (on-demand) - workflows are summaries without stages
export interface ContextDetail extends Omit<Context, 'workflows'> {
  workflows: WorkflowSummary[];
}

// Full context with workflow stages (for session launch)
export interface ContextFull extends Context {
  // workflows: Workflow[] - inherited from Context
}

// ============================================
// Node Types
// ============================================

export interface NodeImage {
  id: number;
  slug: string;
  default_registry: string;
  repository: string;
  default_tag: string;
  metadata: Record<string, unknown>;
  enabled: boolean;
}

// ============================================
// API Response Types
// ============================================

export interface ContextsDetailResponse {
  contexts: { [slug: string]: Context };
  nodes: { [slug: string]: NodeImage };
}

// New response formats
export interface ContextsListResponse {
  contexts: ContextSummary[];
}

export interface ContextDetailResponse extends ContextDetail {}

export interface ContextFullResponse extends ContextFull {}

// ============================================
// Legacy type aliases (for backwards compatibility)
// ============================================

/** @deprecated Use Language instead */
export type ContextLanguage = Language;

// ============================================
// Icon Utilities
// ============================================

export type IconType = 'vue' | 'url' | 'data';

export interface ParsedIcon {
  type: IconType;
  value: string;          // Component path for vue://, URL for others
  componentName?: string; // Extracted component name for vue://
}

/**
 * Parse an icon URL and determine its type.
 *
 * Supported schemes:
 * - vue://components/icons/DataScienceIcon.vue → Vue component
 * - https://... → External URL
 * - data:image/svg+xml;... → Inline data URI
 */
export function parseIconUrl(iconUrl: string | undefined | null): ParsedIcon {
  if (!iconUrl) {
    return { type: 'vue', value: 'components/icons/DataScienceIcon.vue', componentName: 'DataScienceIcon' };
  }

  if (iconUrl.startsWith('vue://')) {
    const path = iconUrl.replace('vue://', '');
    // Extract component name from path like "components/icons/DataScienceIcon.vue"
    const match = path.match(/([^/]+)\.vue$/);
    const componentName = match ? match[1] : undefined;
    return { type: 'vue', value: path, componentName };
  }

  if (iconUrl.startsWith('data:')) {
    return { type: 'data', value: iconUrl };
  }

  // Assume it's a URL (http://, https://, or relative)
  return { type: 'url', value: iconUrl };
}

/**
 * Check if an icon is a Vue component.
 */
export function isVueIcon(iconUrl: string | undefined | null): boolean {
  return parseIconUrl(iconUrl).type === 'vue';
}

/**
 * Get the Vue component name from an icon URL.
 * Returns undefined if not a Vue icon.
 */
export function getVueIconComponent(iconUrl: string | undefined | null): string | undefined {
  const parsed = parseIconUrl(iconUrl);
  return parsed.type === 'vue' ? parsed.componentName : undefined;
}

export const useContextStore = defineStore('context', () => {
  // State
  const contexts = ref<Context[]>([]);
  const nodeImages = ref<Record<string, NodeImage>>({});
  const contextsLoading = ref(false);
  const contextsError = ref<string | null>(null);
  const contextsInitialized = ref(false);
  const contextSummaries = ref<ContextSummary[]>([]);

  // Getters
  const sortedContexts = computed(() =>
    [...contexts.value].sort((a, b) => a.weight - b.weight)
  );

  const enabledContexts = computed(() =>
    contexts.value.filter(c => c.enabled !== false)
  );

  const sortedEnabledContexts = computed(() =>
    [...enabledContexts.value].sort((a, b) => a.weight - b.weight)
  );

  const sortedContextSummaries = computed(() =>
    [...contextSummaries.value].sort((a, b) => a.weight - b.weight)
  );

  const getContextBySlug = computed(() =>
    (slug: string) => contexts.value.find(c => c.slug === slug)
  );

  const getContextById = computed(() =>
    (id: number) => contexts.value.find(c => c.id === id)
  );

  // Actions

  /**
   * Fetch lightweight context summaries for dashboard listing.
   */
  async function fetchContextSummaries(): Promise<void> {
    contextsLoading.value = true;
    contextsError.value = null;

    try {
      const response = await fetch(`${API_BASE_URL}/api/beakerhub/contexts`, {
        credentials: 'include'
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch contexts: ${response.statusText}`);
      }

      const data: ContextsListResponse = await response.json();
      contextSummaries.value = data.contexts;
    } catch (err) {
      console.error('Failed to get context summaries:', err);
      contextsError.value = err instanceof Error ? err.message : 'Failed to load contexts';
      throw err;
    } finally {
      contextsLoading.value = false;
    }
  }

  /**
   * Fetch all contexts with full details (legacy format).
   * Returns dict keyed by slug for backwards compatibility.
   */
  async function fetchContextsDetail(): Promise<void> {
    contextsLoading.value = true;
    contextsError.value = null;

    try {
      const response = await fetch(`${API_BASE_URL}/api/beakerhub/contexts/details`, {
        credentials: 'include'
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch contexts: ${response.statusText}`);
      }

      const data: ContextsDetailResponse = await response.json();
      contexts.value = Object.values(data.contexts);
      nodeImages.value = data.nodes;
      contextsInitialized.value = true;
    } catch (err) {
      console.error('Failed to get contexts detail:', err);
      contextsError.value = err instanceof Error ? err.message : 'Failed to load contexts';
      throw err;
    } finally {
      contextsLoading.value = false;
    }
  }

  /**
   * Fetch a single context by slug with workflow summaries.
   */
  async function fetchContextDetail(slug: string): Promise<ContextDetail> {
    const response = await fetch(`${API_BASE_URL}/api/beakerhub/contexts/${slug}`, {
      credentials: 'include'
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch context: ${response.statusText}`);
    }

    return await response.json();
  }

  /**
   * Fetch a single context by slug with full workflow details including stages.
   */
  async function fetchContextFull(slug: string): Promise<ContextFull> {
    const response = await fetch(`${API_BASE_URL}/api/beakerhub/contexts/${slug}/full`, {
      credentials: 'include'
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch context: ${response.statusText}`);
    }

    return await response.json();
  }

  async function ensureContextsLoaded(): Promise<void> {
    if (contextsInitialized.value || contextsLoading.value) {
      return;
    }
    await fetchContextsDetail();
  }

  return {
    // State
    contexts,
    nodeImages,
    contextsLoading,
    contextsError,
    contextsInitialized,
    contextSummaries,
    // Getters
    sortedContexts,
    enabledContexts,
    sortedEnabledContexts,
    sortedContextSummaries,
    getContextBySlug,
    getContextById,
    // Actions
    fetchContextSummaries,
    fetchContextsDetail,
    fetchContextDetail,
    fetchContextFull,
    ensureContextsLoaded,
  };
});
