import { claimGuard } from '../runtime/guard.js';

export async function installZeroGridHook({ poll, onBeforeRender, onAfterRender }) {
    if (!claimGuard('content:hook:zero-grid')) {
        return false;
    }

    await poll(() => window.zeroGrid != null, 20);

    const originalRender = window.zeroGrid.prototype.render;
    const originalRenderData = window.zeroGrid.prototype.renderData;

    window.zeroGrid.prototype.render = function (...args) {
        onBeforeRender?.(this);
        return originalRender.apply(this, args);
    };

    window.zeroGrid.prototype.renderData = function (...args) {
        const result = originalRenderData.apply(this, args);
        onAfterRender?.(this, args[0]);
        return result;
    };

    window.zynkc_zeroGrid?.render?.();
    return true;
}
