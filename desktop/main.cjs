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
if (process.platform === 'darwin') {
  const homebrewPaths = ['/opt/homebrew/bin', '/usr/local/bin', '/opt/homebrew/opt/node/bin', '/usr/local/opt/node/bin'];
  config.PATH = [...homebrewPaths.filter((entry) => fs.existsSync(entry)), config.PATH || '/usr/bin:/bin:/usr/sbin:/sbin'].join(path.delimiter);
}
const rawPort = config.HYPE_PORT || '8787';
const port = /^\d+$/.test(rawPort) ? Number(rawPort) : 0;
const validPort = Number.isInteger(port) && port >= 1024 && port <= 65535;
const origin = `http://127.0.0.1:${port}`;
let backend;
let backendFailure;
let mainWindow;
let quitting = false;
let quitCheckInProgress = false;
let shutdownFinished = false;
let startupFailed = false;
let backendGroupPid;
let logStream;

function serviceError(message) {
  const error = new Error(message);
  error.code = 'EINVALIDSERVICE';
  return error;
}

function readJson(route, maxBytes = 512000) {
  return new Promise((resolve, reject) => {
    const request = http.get(`${origin}${route}`, { timeout: 1800 }, (response) => {
      let body = '';
      response.setEncoding('utf8');
      response.on('data', (chunk) => {
        body += chunk;
        if (body.length > maxBytes) request.destroy(serviceError('Yerel sunucunun yanıtı beklenenden büyük.'));
      });
      response.on('error', reject);
      response.on('end', () => {
        if (response.statusCode !== 200) return reject(serviceError(`${port} numaralı portta uyumlu Hype Studio sunucusu yanıt vermedi.`));
        try {
          resolve(JSON.parse(body));
        } catch {
          reject(serviceError(`${port} numaralı portu başka bir uygulama kullanıyor.`));
        }
      });
    });
    request.on('timeout', () => request.destroy(serviceError(`${port} numaralı porttaki sunucu yanıt vermiyor. Çalışan sunucuyu kontrol edin veya farklı bir HYPE_PORT kullanın.`)));
    request.on('error', reject);
  });
}

function canonicalPath(value) {
  const resolved = path.resolve(projectRoot, value);
  try { return fs.realpathSync(resolved); } catch { return resolved; }
}

async function readStatus() {
  const status = await readJson('/api/status');
  if (status?.app !== 'hype-studio') throw serviceError(`${port} numaralı portu başka bir uygulama kullanıyor.`);
  if (status.api_version !== 4) {
    throw serviceError(`${port} numaralı portta eski veya uyumsuz Hype Studio sunucusu çalışıyor. Açık sunucuyu durdurup uygulamayı yeniden başlatın.`);
  }
  const expectedDataDir = config.HYPE_DATA_DIR || path.join(app.getPath('userData'), 'data');
  if (typeof status.project_root !== 'string' || typeof status.data_dir !== 'string'
      || canonicalPath(status.project_root) !== canonicalPath(projectRoot)
      || canonicalPath(status.data_dir) !== canonicalPath(expectedDataDir)) {
    throw serviceError(`${port} numaralı portta farklı proje veya veri klasörü kullanan Hype Studio çalışıyor. Açık sunucuyu durdurun ya da HYPE_DATA_DIR ve HYPE_PORT ayarlarını eşleştirin.`);
  }
  return status;
}

async function startBackend() {
  try {
    await readStatus();
    return;
  } catch (error) {
    if (error.code !== 'ECONNREFUSED') throw error;
  }

  const venvPython = path.join(projectRoot, '.venv', 'bin', 'python');
  const python = fs.existsSync(venvPython) ? venvPython : config.HYPE_PYTHON;
  if (!python || !fs.existsSync(python)) {
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
    detached: process.platform !== 'win32',
  });
  backendGroupPid = process.platform !== 'win32' ? backend.pid : undefined;
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
      if (error.code === 'EINVALIDSERVICE') throw error;
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
  mainWindow.on('close', (event) => {
    if (!shutdownFinished) {
      event.preventDefault();
      void requestQuit();
    }
  });
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
    startupFailed = true;
    dialog.showErrorBox('Hype Studio başlatılamadı', error.message);
    app.quit();
  });
}

app.on('window-all-closed', () => app.quit());
app.on('before-quit', (event) => {
  if (shutdownFinished || !hasLock) return;
  event.preventDefault();
  void requestQuit();
});

function ownedBackendAlive() {
  if (!backend) return false;
  if (backendGroupPid) {
    try { process.kill(-backendGroupPid, 0); return true; } catch { return false; }
  }
  return backend.exitCode === null && backend.signalCode === null && Boolean(backend.pid);
}

function signalOwnedBackend(signal) {
  if (!backend) return;
  try {
    if (backendGroupPid) process.kill(-backendGroupPid, signal);
    else if (backend.pid) backend.kill(signal);
  } catch (error) {
    if (error.code !== 'ESRCH') throw error;
  }
}

async function stopOwnedBackend() {
  if (!backend) return;
  signalOwnedBackend('SIGTERM');
  const deadline = Date.now() + 1800;
  while (ownedBackendAlive() && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 60));
  }
  if (ownedBackendAlive()) signalOwnedBackend('SIGKILL');
  backendGroupPid = undefined;
  logStream?.end();
}

async function requestQuit() {
  if (quitCheckInProgress || quitting) return;
  quitCheckInProgress = true;
  try {
    if (!startupFailed && !backendFailure) {
      let busy = 0;
      let unavailable = false;
      try {
        const projects = await readJson('/api/projects', 8 * 1024 * 1024);
        if (!Array.isArray(projects.items)) throw new Error('Geçersiz proje listesi.');
        busy = projects.items.filter((project) => ['queued', 'rendering', 'translating', 'uploading', 'processing_audio'].includes(project.status)).length;
      } catch {
        unavailable = true;
      }
      if (busy || unavailable) {
        const detail = unavailable
          ? 'Devam eden işlem durumu alınamadı. Çıkarsanız uygulamanın başlattığı üretim, çeviri, ses işleme veya yükleme işlemleri durdurulur.'
          : backend
            ? `${busy} proje sırada veya işleniyor. Çıkarsanız video üretimi, Türkçe çeviri, ses işleme veya YouTube yüklemesi yarıda kalabilir.`
            : `${busy} proje sırada veya işleniyor. Bu pencereyi kapattığınızda ayrı başlatılan sunucudaki işlemler devam eder.`;
        const options = {
          type: 'question',
          title: 'Hype Studio kapatılsın mı?',
          message: unavailable ? 'İşlem durumu kontrol edilemedi.' : 'Devam eden işler var.',
          detail,
          buttons: ['Çalışmaya devam et', 'Çık'],
          defaultId: 0,
          cancelId: 0,
          noLink: true,
        };
        const result = mainWindow ? await dialog.showMessageBox(mainWindow, options) : await dialog.showMessageBox(options);
        if (result.response !== 1) return;
      }
    }
    quitting = true;
    await stopOwnedBackend();
    shutdownFinished = true;
    app.quit();
  } catch (error) {
    quitting = false;
    dialog.showErrorBox('Hype Studio kapatılamadı', error.message);
  } finally {
    quitCheckInProgress = false;
  }
}
