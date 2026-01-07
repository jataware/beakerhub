import { describe, it, expect } from 'vitest';
import {
  SECRET_POLICY_AXES,
  SECRET_POLICY_DEFAULTS,
  ENVIRONMENT_POLICY_OPTIONS,
  effectivePolicy,
  overrideCount,
  pruneDefaults,
  type SecretPolicies,
} from '@/utils/secretPolicies';

describe('secretPolicies', () => {
  describe('defaults', () => {
    it('matches the upstream SystemEnvironmentSecret defaults', () => {
      expect(SECRET_POLICY_DEFAULTS).toEqual({
        ui_message_policy: 'redact',
        agent_message_policy: 'redact',
        subkernel_message_policy: 'redact',
        beaker_kernel_environment_policy: 'allow',
        subkernel_environment_policy: 'remove',
      });
    });

    it('covers all five policy axes', () => {
      expect(SECRET_POLICY_AXES).toHaveLength(5);
    });

    it('offers only allow/remove for the environment axes', () => {
      const envAxes = SECRET_POLICY_AXES.filter(axis => axis.key.endsWith('environment_policy'));
      expect(envAxes).toHaveLength(2);
      for (const axis of envAxes) {
        expect(axis.options).toBe(ENVIRONMENT_POLICY_OPTIONS);
        expect(axis.options.map(o => o.value)).toEqual(['allow', 'remove']);
      }
    });

    it('offers all four policy types for the message axes', () => {
      const messageAxes = SECRET_POLICY_AXES.filter(axis => axis.key.endsWith('message_policy'));
      expect(messageAxes).toHaveLength(3);
      for (const axis of messageAxes) {
        expect(axis.options.map(o => o.value).sort()).toEqual(['allow', 'last4', 'redact', 'remove']);
      }
    });
  });

  describe('effectivePolicy', () => {
    it('falls back to the default when the axis is absent', () => {
      expect(effectivePolicy({}, 'subkernel_environment_policy')).toBe('remove');
      expect(effectivePolicy(null, 'beaker_kernel_environment_policy')).toBe('allow');
      expect(effectivePolicy(undefined, 'ui_message_policy')).toBe('redact');
    });

    it('returns the override when present', () => {
      const policies: SecretPolicies = { subkernel_environment_policy: 'allow' };
      expect(effectivePolicy(policies, 'subkernel_environment_policy')).toBe('allow');
    });
  });

  describe('overrideCount', () => {
    it('is zero for an empty or missing dict', () => {
      expect(overrideCount({})).toBe(0);
      expect(overrideCount(null)).toBe(0);
      expect(overrideCount(undefined)).toBe(0);
    });

    it('ignores entries that merely restate the default', () => {
      expect(overrideCount({ subkernel_environment_policy: 'remove' })).toBe(0);
    });

    it('counts entries that deviate from the default', () => {
      expect(
        overrideCount({
          subkernel_environment_policy: 'allow',
          ui_message_policy: 'last4',
        }),
      ).toBe(2);
    });
  });

  describe('pruneDefaults', () => {
    it('keeps only genuine overrides', () => {
      const pruned = pruneDefaults({
        subkernel_environment_policy: 'allow',
        beaker_kernel_environment_policy: 'allow', // same as default
        agent_message_policy: 'remove',
      });
      expect(pruned).toEqual({
        subkernel_environment_policy: 'allow',
        agent_message_policy: 'remove',
      });
    });

    it('yields an empty dict when everything is default', () => {
      expect(pruneDefaults({ ui_message_policy: 'redact' })).toEqual({});
    });
  });

  describe('axis options', () => {
    it('never lists the same policy value twice, so the default appears once', () => {
      for (const axis of SECRET_POLICY_AXES) {
        const values = axis.options.map(o => o.value);
        expect(values).toEqual([...new Set(values)]);
        expect(values).toContain(axis.defaultValue);
      }
    });
  });
});
