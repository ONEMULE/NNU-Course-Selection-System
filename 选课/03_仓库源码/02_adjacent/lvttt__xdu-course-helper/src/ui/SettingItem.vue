<template>
    <div class="py-3 border-b border-gray-100 last:border-0 flex flex-col gap-2">
        <div class="flex items-center justify-between">
            <div class="pr-4">
                <h2 class="text-[13px] font-semibold text-gray-800">{{ title }}</h2>
                <p v-if="description" class="text-[11px] text-gray-500 leading-tight mt-1">
                    {{ description }}
                </p>
            </div>
            <div class="shrink-0 flex items-center">
                <slot name="action"></slot>
            </div>
        </div>

        <div v-if="$slots.warning" class="mt-1">
            <slot name="warning"></slot>
        </div>

        <div v-if="$slots.default" class="mt-1">
            <slot></slot>
        </div>
    </div>
</template>

<script setup>
defineProps({
    title: String,
    description: String,
});
</script>
