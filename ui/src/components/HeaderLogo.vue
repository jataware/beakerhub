<template>
    <div class="logo-section" :class="[`size-${props.size}`]">
        <BeakerHubLogo :class="['logo', `size-${props.size}`]"/>
        <h2 class="brand-name">BeakerHub</h2>
    </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRouter } from 'vue-router';

import BeakerHubLogo from './BeakerHubLogo.vue';

interface Props {
    size?: "minimal"|"small"|"medium"|"large";
}

const props = withDefaults(defineProps<Props>(), {
    size: "medium"
});

</script>


<style scoped lang="scss">
.logo-section {
    display: flex;
    align-items: center;
    gap: 1rem;
    border-radius: 0.5rem;
    padding: 0.5rem 1rem;

    &.size-small {
        padding: 0.25rem 0.5rem;
        .logo {
            max-height: 3rem;
            max-width: 3rem;
        }
    }

    &.size-minimal {
        padding: 0.25rem 0rem;

        .logo {
            max-height: 2rem;
            max-width: 2rem;
        }

        .brand-name {
            font-size: 1.5rem;
        }
    }

    &.link{
        cursor: pointer;

        &:hover {
            background-color: rgba(127, 127, 127, 0.2);
        }
    }
}


.brand-name {
    font-size: 2rem;
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
