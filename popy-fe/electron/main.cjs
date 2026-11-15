const { app, BrowserWindow, shell, Menu } = require('electron');
const path = require('path');
const { startStack, stopStack } = require('./supervisor.cjs');

let stackStarted = false;
const devServerUrl = process.env.ELECTRON_START_URL || 'http://localhost:5173';

let mainWindow = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1360,
    height: 860,
    minWidth: 1024,
    minHeight: 700,
    title: 'Popy POS',
    backgroundColor: '#0E192B',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false,
      webSecurity: true,
    },
  });

  // Gracefully show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Open external links in default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http://') || url.startsWith('https://')) {
      shell.openExternal(url);
    }
    return { action: 'deny' };
  });

  if (!app.isPackaged) {
    mainWindow.loadURL(devServerUrl).catch(() => {
      console.log('Dev server not ready yet, retrying in 1s...');
      setTimeout(() => {
        mainWindow.loadURL(devServerUrl);
      }, 1000);
    });
    if (process.env.OPEN_DEVTOOLS === 'true') {
      mainWindow.webContents.openDevTools();
    }
  } else {
    mainWindow.loadFile(path.join(__dirname, 'starting.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  setupMenu();
}

function setupMenu() {
  const isMac = process.platform === 'darwin';
  const template = [
    ...(isMac
      ? [
          {
            label: app.name,
            submenu: [
              { role: 'about' },
              { type: 'separator' },
              { role: 'services' },
              { type: 'separator' },
              { role: 'hide' },
              { role: 'hideOthers' },
              { role: 'unhide' },
              { type: 'separator' },
              { role: 'quit' },
            ],
          },
        ]
      : []),
    {
      label: 'File',
      submenu: [isMac ? { role: 'close' } : { role: 'quit' }],
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectAll' },
      ],
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'Popy Documentation',
          click: async () => {
            await shell.openExternal('https://github.com');
          },
        },
      ],
    },
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

// Single instance lock
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  const showStartError = (error) => {
    const message = String(error && error.message ? error.message : error)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;');
    const html = `<!DOCTYPE html><html><body style="margin:0;min-height:100vh;display:grid;place-items:center;background:#0e192b;color:#e8eef8;font:15px/1.5 Segoe UI,sans-serif"><main style="max-width:560px;padding:24px"><h1 style="font-size:22px">Popy could not start</h1><pre style="white-space:pre-wrap;color:#f3c1c1">${message}</pre><p style="color:#b7c3d6">Details are in %LOCALAPPDATA%\\Popy POS\\logs\\desktop.log</p></main></body></html>`;
    if (mainWindow) {
      mainWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(html)}`);
    }
  };

  app.whenReady().then(async () => {
    createWindow();

    if (app.isPackaged) {
      try {
        const { apiUrl } = await startStack();
        stackStarted = true;
        await mainWindow.loadURL(`${apiUrl}/#/login`);
      } catch (error) {
        await stopStack().catch(() => undefined);
        showStartError(error);
      }
    }

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
      }
    });
  });

  app.on('before-quit', (event) => {
    if (!stackStarted) return;
    event.preventDefault();
    stackStarted = false;
    stopStack()
      .catch(() => undefined)
      .finally(() => app.quit());
  });
}

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
