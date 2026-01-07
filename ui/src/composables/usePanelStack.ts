import { computed, ref, watch, type Ref } from 'vue';

export interface PanelDef {
  key: string;
  label: string;
  component: string;
}

export interface PanelLayout {
  key: string;
  label: string;
  component: string;
  width: string;
  collapsed: boolean;
}

const PEEK_WIDTH = '60px';

export function usePanelStack(panels: Ref<PanelDef[]>) {
  const previousCount = ref(0);
  const transitionDirection = ref<'forward' | 'backward'>('forward');

  watch(
    () => panels.value.length,
    (newCount, oldCount) => {
      transitionDirection.value = newCount > (oldCount ?? 0) ? 'forward' : 'backward';
      previousCount.value = oldCount ?? 0;
    },
  );

  const layouts = computed<PanelLayout[]>(() => {
    const count = panels.value.length;
    return panels.value.map((panel, index) => {
      const isLast = index === count - 1;
      const isSecondToLast = index === count - 2;

      let width: string;
      let collapsed = false;

      if (count === 1) {
        width = '100%';
      } else if (count === 2) {
        width = '50%';
      } else {
        // 3+ panels
        if (isLast || isSecondToLast) {
          width = `calc((100% - ${PEEK_WIDTH} * ${count - 2}) / 2)`;
        } else {
          width = PEEK_WIDTH;
          collapsed = true;
        }
      }

      return {
        key: panel.key,
        label: panel.label,
        component: panel.component,
        width,
        collapsed,
      };
    });
  });

  return {
    layouts,
    transitionDirection,
  };
}
