const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('windowControls', {
  minimize: () => ipcRenderer.invoke('window-minimize'),
  maximize: () => ipcRenderer.invoke('window-maximize'),
  isMaximized: () => ipcRenderer.invoke('window-is-maximized'),
  close: () => ipcRenderer.invoke('window-close'),
  onMaximized: (callback) => ipcRenderer.on('window-maximized', callback),
  onUnmaximized: (callback) => ipcRenderer.on('window-unmaximized', callback),
  onWindowWillClose: (callback) => ipcRenderer.on('window-will-close', callback),
  removeMaximizedListeners: () => {
    ipcRenderer.removeAllListeners('window-maximized')
    ipcRenderer.removeAllListeners('window-unmaximized')
  },
  removeWindowWillCloseListener: () => {
    ipcRenderer.removeAllListeners('window-will-close')
  }
})

