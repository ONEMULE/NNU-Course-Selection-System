const GLOBAL_GUARD_KEY = '__xdu_course_helper_guards__';

function getGuardStore() {
    if (!window[GLOBAL_GUARD_KEY]) {
        window[GLOBAL_GUARD_KEY] = {};
    }
    return window[GLOBAL_GUARD_KEY];
}

export function claimGuard(key) {
    const guards = getGuardStore();
    if (guards[key]) {
        return false;
    }
    guards[key] = true;
    return true;
}
