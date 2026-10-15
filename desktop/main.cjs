'use strict';

const { app, BrowserWindow, dialog, shell, session } = require('electron');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { parseEnv } = require('node:util');

app.setName('Hype Studio');
app.enableSandbox();

const projectRoot = path.resolve(__dirname, '..');
let fileConfig = {};
let configError;
try {
  const configPath = path.join(projectRoot, '.env');
  if (fs.existsSync(configPath)) fileConfig = parseEnv(fs.readFileSync(configPath, 'utf8'));
} catch {
  configError = new Error('Proje içindeki .env dosyası okunamadı. Dosya izinlerini ve biçimini kontrol edin.');
}
const config = { ...fileConfig, ...process.env };
const rawPort = config.HYPE_PORT || '8787';
const port = /^\d+$/.test(rawPort) ? Number(rawPort) : 0;
const validPort = Number.isInteger(port) && port >= 1024 && port <= 65535;
const origin = `http://127.0.0.1:${port}`;
let backend;
let backendFailure;
let mainWindow;
let quitting = false;
let logStream;

function readStatus() {
  return new Promise((resolve, reject) => {
    const request = http.get(`${origin}/api/status`, { timeout: 1200 }, (response) => {
      let body = '';
      response.setEncoding('utf8');
      response.on('data', (chunk) => {
        body += chunk;
        if (body.length > 512000) request.destroy(new Error('Durum yanıtı çok büyük.'));
      });
      response.on('error', reject);
      response.on('end', () => {
        if (response.statusCode !== 200) return reject(new Error('Sunucu hazır değil.'));
        try {
          const status = JSON.parse(body);
          if (status.app !== 'hype-studio') {
            return reject(new Error(`${port} numaralı portu başka bir uygulama kullanıyor.`));
          }
          resolve(status);
        } catch (error) {
          reject(error);
        }
      });
    });
    request.on('timeout', () => request.destroy(new Error('Sunucu yanıt vermedi.')));
    request.on('error', reject);
  });
}

async function startBackend() {
  try {
    await readStatus();
    return;
  } catch (error) {
    if (error.message.includes('başka bir uygulama')) throw error;
  }

  const python = config.HYPE_PYTHON || path.join(projectRoot, '.venv', 'bin', 'python');
  if (!fs.existsSync(python)) {
    throw new Error('Python ortamı bulunamadı. Proje klasöründe önce ./scripts/setup.sh komutunu çalıştırın.');
  }
  const logPath = path.join(app.getPath('logs'), 'hype-studio-backend.log');
  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  if (fs.existsSync(logPath) && fs.statSync(logPath).size > 2 * 1024 * 1024) {
    fs.renameSync(logPath, `${logPath}.previous`);
  }
  logStream = fs.createWriteStream(logPath, { flags: 'a', mode: 0o600 });
  logStream.on('error', () => {});

  backend = spawn(python, ['-m', 'app.server'], {
    cwd: projectRoot,
    env: {
      ...config,
      HYPE_PORT: String(port),
      HYPE_DATA_DIR: config.HYPE_DATA_DIR || path.join(app.getPath('userData'), 'data'),
      PYTHONUNBUFFERED: '1',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
    shell: false,
  });
  backend.stdout.pipe(logStream, { end: false });
  backend.stderr.pipe(logStream, { end: false });
  backend.on('error', (error) => { backendFailure = error; });
  backend.on('exit', (code, signal) => {
    backendFailure = new Error(`Yerel sunucu kapandı (${signal || code}). Günlük: ${logPath}`);
    if (mainWindow && !quitting) {
      dialog.showErrorBox('Hype Studio sunucusu kapandı', backendFailure.message);
      app.quit();
    }
  });

  const deadline = Date.now() + 45000;
  while (Date.now() < deadline) {
    if (backendFailure) throw backendFailure;
    try {
      await readStatus();
      return;
    } catch (error) {
      if (error.message.includes('başka bir uygulama')) throw error;
      await new Promise((resolve) => setTimeout(resolve, 300));
    }
  }
  throw new Error(`Yerel sunucu 45 saniyede açılamadı. Günlük: ${logPath}`);
}

function isLocalNavigation(url) {
  try { return new URL(url).origin === origin; } catch { return false; }
}

function openSecureExternal(url) {
  try {
    const parsed = new URL(url);
    if (parsed.protocol === 'https:' && !parsed.username && !parsed.password) {
      shell.openExternal(parsed.href).catch(() => {});
    }
  } catch {}
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1500,
    height: 980,
    minWidth: 1080,
    minHeight: 740,
    title: 'Hype Studio',
    backgroundColor: '#13151d',
    show: false,
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    trafficLightPosition: { x: 22, y: 22 },
    vibrancy: process.platform === 'darwin' ? 'under-window' : undefined,
    visualEffectState: 'active',
    roundedCorners: true,
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      devTools: !app.isPackaged,
    },
  });
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    openSecureExternal(url);
    return { action: 'deny' };
  });
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (!isLocalNavigation(url)) {
      event.preventDefault();
      openSecureExternal(url);
    }
  });
  mainWindow.webContents.on('will-attach-webview', (event) => event.preventDefault());
  mainWindow.once('ready-to-show', () => mainWindow.show());
  mainWindow.on('closed', () => { mainWindow = null; });
  mainWindow.loadURL(origin);
}

const hasLock = app.requestSingleInstanceLock();
if (!hasLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
  app.whenReady().then(async () => {
    if (configError) throw configError;
    if (!validPort) throw new Error('HYPE_PORT 1024–65535 arasında bir sayı olmalıdır.');
    session.defaultSession.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false));
    session.defaultSession.setPermissionCheckHandler(() => false);
    await startBackend();
    createWindow();
  }).catch((error) => {
    dialog.showErrorBox('Hype Studio başlatılamadı', error.message);
    app.quit();
  });
}

app.on('window-all-closed', () => app.quit());
app.on('before-quit', (event) => {
  if (quitting || !backend || backend.exitCode !== null || backend.signalCode !== null) return;
  event.preventDefault();
  quitting = true;
  const timeout = setTimeout(() => {
    if (backend.exitCode === null) backend.kill('SIGKILL');
    logStream?.end();
    app.quit();
  }, 1800);
  backend.once('exit', () => {
    clearTimeout(timeout);
    logStream?.end();
    app.quit();
  });
  backend.kill('SIGTERM');
});
