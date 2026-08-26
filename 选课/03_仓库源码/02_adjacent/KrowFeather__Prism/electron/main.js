const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');

const createWindow = () => {
    const win = new BrowserWindow({
        width: 1100,
        height: 650,
        frame: false,
        titleBarStyle: 'hidden',
        title: 'Prism',
        autoHideMenuBar: true,
        movable: true,
        resizable: true,
        minimizable: true,
        maximizable: true,
        fullscreenable: false,
        useContentSize: true,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
            devTools: true
        }
    });
    // 根据环境加载不同的内容
    if (app.isPackaged) {
        // 生产环境：加载打包后的文件
        // electron-builder 会将 dist 文件夹打包到应用根目录
        // __dirname 在打包后指向 resources/app/electron，所以需要上一级目录
        win.loadFile(path.join(__dirname, '../dist/index.html'));
    } else {
        // 开发环境：加载开发服务器
        win.loadURL("http://localhost:3000");
        // 开发模式下自动打开开发者工具
        win.webContents.openDevTools();
    }

    return win;
};

app.whenReady().then(() => {
    const win = createWindow();
    win.maximize();

    ipcMain.handle('window-minimize', () => {
        if (win) {
            win.minimize();
        }
    });

    ipcMain.handle('window-maximize', () => {
        if (win) {
            if (win.isMaximized()) {
                win.unmaximize();
            } else {
                win.maximize();
            }
        }
    });

    ipcMain.handle('window-is-maximized', () => {
        if (win) {
            return win.isMaximized();
        }
        return false;
    });

    ipcMain.handle('window-close', () => {
        if (win) {
            win.close();
        }
    });

    win.on('maximize', () => {
        win.webContents.send('window-maximized');
    });

    win.on('unmaximize', () => {
        win.webContents.send('window-unmaximized');
    });

    // 监听窗口关闭事件，通知前端清除登录状态
    win.on('close', (event) => {
        // 只有在真正关闭窗口时才发送消息
        // 发送关闭事件给前端，让前端清理登录状态
        if (!win.isDestroyed()) {
            win.webContents.send('window-will-close');
        }
        // 不阻止关闭，正常关闭窗口
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});