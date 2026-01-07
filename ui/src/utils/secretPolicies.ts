/**
 * Secret policy metadata, mirroring the policy framework in beaker-notebook
 * (`beaker_notebook.lib.secrets`).
 *
 * Vault secrets are all system secrets for now, so the defaults below are those of
 * upstream's `SystemEnvironmentSecret`. A secret stores only *overrides* against those
 * defaults: an axis absent from the policies dict means "use the default".
 *
 * See .plans/secrets-framework-background.md for the full picture.
 */

/** Values accepted by upstream's `PolicyTypes`. */
export type SecretPolicyType = 'allow' | 'redact' | 'remove' | 'last4';

/** The five policy fields on upstream's `BaseSecret`. */
export type SecretPolicyAxis =
  | 'ui_message_policy'
  | 'agent_message_policy'
  | 'subkernel_message_policy'
  | 'beaker_kernel_environment_policy'
  | 'subkernel_environment_policy';

/** Sparse override map stored alongside a vault secret. Absent key = default. */
export type SecretPolicies = Partial<Record<SecretPolicyAxis, SecretPolicyType>>;

export interface SecretPolicyOption {
  value: SecretPolicyType;
  label: string;
  description: string;
}

export interface SecretPolicyAxisDefinition {
  key: SecretPolicyAxis;
  label: string;
  description: string;
  /** Upstream `SystemEnvironmentSecret` default for this axis. */
  defaultValue: SecretPolicyType;
  options: SecretPolicyOption[];
  /** Optional caveat surfaced in the editor. */
  note?: string;
}

/**
 * Policies for message scrubbing. All four are meaningful: the secret's value is
 * rewritten in place within the message payload.
 */
export const MESSAGE_POLICY_OPTIONS: SecretPolicyOption[] = [
  { value: 'redact', label: 'Redact', description: 'Replace the value with # characters.' },
  { value: 'last4', label: 'Last 4', description: 'Mask all but the last four characters.' },
  { value: 'remove', label: 'Remove', description: 'Replace the value with an empty string.' },
  { value: 'allow', label: 'Allow', description: 'Pass the value through unmodified.' },
];

/**
 * Policies for environment variables. Only allow/remove are offered: any other policy
 * rewrites the variable's value in place, which for a credential means breaking it.
 */
export const ENVIRONMENT_POLICY_OPTIONS: SecretPolicyOption[] = [
  { value: 'allow', label: 'Allow', description: 'Set the environment variable to its real value.' },
  { value: 'remove', label: 'Remove', description: 'Do not set the environment variable at all.' },
];

export const SECRET_POLICY_AXES: SecretPolicyAxisDefinition[] = [
  {
    key: 'beaker_kernel_environment_policy',
    label: 'Beaker kernel environment',
    description: 'Whether the Beaker kernel process gets this value as an environment variable.',
    defaultValue: 'allow',
    options: ENVIRONMENT_POLICY_OPTIONS,
  },
  {
    key: 'subkernel_environment_policy',
    label: 'Subkernel environment',
    description:
      "Whether the user's subkernel process gets this value as an environment variable. " +
      'Allow this for shared keys the user\'s tooling needs; remove it for keys that must stay private.',
    defaultValue: 'remove',
    options: ENVIRONMENT_POLICY_OPTIONS,
  },
  {
    key: 'ui_message_policy',
    label: 'UI messages',
    description: 'How the value is scrubbed from Jupyter messages sent to the browser.',
    defaultValue: 'redact',
    options: MESSAGE_POLICY_OPTIONS,
  },
  {
    key: 'subkernel_message_policy',
    label: 'Subkernel messages',
    description: 'How the value is scrubbed from Jupyter messages sent to the subkernel.',
    defaultValue: 'redact',
    options: MESSAGE_POLICY_OPTIONS,
  },
  {
    key: 'agent_message_policy',
    label: 'Agent messages',
    description: 'How the value is scrubbed from content handed to the LLM agent.',
    defaultValue: 'redact',
    options: MESSAGE_POLICY_OPTIONS,
    note: 'Stored now, but not yet enforced by the notebook server.',
  },
];

/** Defaults keyed by axis, derived from the axis definitions. */
export const SECRET_POLICY_DEFAULTS: Record<SecretPolicyAxis, SecretPolicyType> =
  SECRET_POLICY_AXES.reduce(
    (acc, axis) => {
      acc[axis.key] = axis.defaultValue;
      return acc;
    },
    {} as Record<SecretPolicyAxis, SecretPolicyType>,
  );

/** The policy actually in force for an axis, falling back to the default. */
export function effectivePolicy(
  policies: SecretPolicies | null | undefined,
  axis: SecretPolicyAxis,
): SecretPolicyType {
  return policies?.[axis] ?? SECRET_POLICY_DEFAULTS[axis];
}

/** How many axes are explicitly overridden. Values equal to the default do not count. */
export function overrideCount(policies: SecretPolicies | null | undefined): number {
  if (!policies) {
    return 0;
  }
  return SECRET_POLICY_AXES.filter(
    axis => policies[axis.key] !== undefined && policies[axis.key] !== axis.defaultValue,
  ).length;
}

/** Drop any entry that merely restates the default, keeping the stored dict sparse. */
export function pruneDefaults(policies: SecretPolicies): SecretPolicies {
  const result: SecretPolicies = {};
  for (const axis of SECRET_POLICY_AXES) {
    const value = policies[axis.key];
    if (value !== undefined && value !== axis.defaultValue) {
      result[axis.key] = value;
    }
  }
  return result;
}
