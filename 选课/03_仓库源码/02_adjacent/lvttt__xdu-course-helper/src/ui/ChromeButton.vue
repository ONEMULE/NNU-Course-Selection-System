<template>
    <button
        @click="$emit('click')"
        :disabled="disabled"
        :class="[
            'px-3 py-1.5 text-[12px] font-medium rounded transition-colors flex items-center justify-center gap-1.5 cursor-pointer',
            block ? 'w-full' : '',
            variant === 'primary'
                ? 'bg-blue-600 text-white hover:bg-blue-700 disabled:bg-blue-300 disabled:cursor-not-allowed'
                : '',
            variant === 'secondary'
                ? 'bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:bg-gray-50 border border-gray-200'
                : '',
            variant === 'danger'
                ? 'bg-red-50 text-red-600 hover:bg-red-100 border border-red-100'
                : '',
        ]"
    >
        <slot></slot>
    </button>
</template>

<script setup>
defineProps({
    variant: { type: String, default: 'primary' }, // primary, secondary, danger
    disabled: { type: Boolean, default: false },
    block: { type: Boolean, default: false },
});
defineEmits(['click']);
</script>
