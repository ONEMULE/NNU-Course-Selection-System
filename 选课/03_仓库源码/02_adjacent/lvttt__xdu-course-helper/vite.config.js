import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import tailwindcss from '@tailwindcss/vite';
import { crx } from '@crxjs/vite-plugin';
import manifest from './manifest.json';

export default defineConfig({
    plugins: [vue(), tailwindcss(), crx({ manifest })],
    server: {
        cors: {
            origin: [
                /chrome-extension:\/\//,
            ],
        },
    },
});
