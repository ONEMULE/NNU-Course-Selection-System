<template>
    <label class="relative inline-flex items-center cursor-pointer">
        <input
            type="checkbox"
            :checked="modelValue"
            @change="$emit('update:modelValue', $event.target.checked)"
            class="sr-only peer"
        />
        <div
            class="w-8 h-4 bg-gray-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-4 peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-3 after:w-3 after:transition-all peer-checked:bg-blue-600"
        ></div>
    </label>
</template>

<script setup>
defineProps({
    modelValue: {
        type: Boolean,
        default: false,
    },
});
defineEmits(['update:modelValue']);
</script>
