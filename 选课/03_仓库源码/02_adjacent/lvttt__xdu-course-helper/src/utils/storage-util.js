// src/utils/storage-util.js
import { getStorageValue, setStorageValue } from '../shared/chrome-storage';

export async function getStorage(key) {
    return getStorageValue(key);
}

export async function setStorage(key, value) {
    return setStorageValue(key, value);
}
