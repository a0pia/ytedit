'use strict';

// Exercise the actual Electron main module with OS, HTTP and window boundaries
// replaced. These tests need no graphical session, Electron binary or network.
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const projectRoot = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(projectRoot, 'desktop/main.cjs'), 'utf8');

function desktop(t, env = {}) {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'hype-desktop-test-'));
  t.after(() => fs.rmSync(temporary, { recursive: true, force: true }));
  const app = new EventEmitter();
  const state = {
    exits: 0, signals: [], spawns: [], dialogs: [], windows: [], choice: 0,
    alive: true, firstError: null, projects: { items: [] },
    status: { app: 'hype-studio', api_version: 2, project_root: projectRoot,
      data_dir: path.join(temporary, 'userData', 'data') },
  };
  app.setName = () => {};
  app.enableSandbox = () => {};
  app.isPackaged = false;
  app.getPath = (kind) => path.join(temporary, kind);
  app.requestSingleInstanceLock = () => true;
  // Startup is invoked explicitly by each test, avoiding an actual event loop.
  app.whenReady = () => new Promise(() => {});
  app.quit = () => {
    const event = { prevented: false, preventDefault() { this.prevented = true; } };
    app.emit('before-quit', event);
    if (!event.prevented) state.exits++;
  };

  class Window extends EventEmitter {
    constructor(options) {
      super();
      this.options = options;
      this.webContents = new EventEmitter();
      this.webContents.setWindowOpenHandler = () => {};
      state.windows.push(this);
    }
    loadURL() {}
    show() {}
  }
  const electron = {
    app, BrowserWindow: Window, session: { defaultSession: {} },
    shell: { openExternal: async () => {} },
    dialog: {
      showErrorBox: (...args) => { assert.fail(args.join(': ')); },
      showMessageBox: async (...args) => {
        state.dialogs.push(args.at(-1));
        return { response: state.choice };
      },
    },
  };
  const http = {
    get(url, _options, callback) {
      const request = new EventEmitter();
      request.destroy = (error) => request.emit('error', error);
      queueMicrotask(() => {
        if (state.firstError) {
          const error = state.firstError;
          state.firstError = null;
          request.emit('error', error);
          return;
        }
        const response = new EventEmitter();
        response.statusCode = 200;
        response.setEncoding = () => {};
        callback(response);
        response.emit('data', JSON.stringify(url.endsWith('/api/projects') ? state.projects : state.status));
        response.emit('end');
      });
      return request;
    },
  };
  const spawn = (...args) => {
    state.spawns.push(args);
    const child = new EventEmitter();
    Object.assign(child, { pid: 3210, exitCode: null, signalCode: null,
      stdout: { pipe() {} }, stderr: { pipe() {} } });
    child.kill = (signal) => state.signals.push([child.pid, signal]);
    return child;
  };
  const fakeFs = {
    ...fs,
    existsSync(filename) {
      if (filename === path.join(projectRoot, '.env')) return false;
      if (filename === path.join(projectRoot, '.venv/bin/python')) return true;
      return fs.existsSync(filename);
    },
    createWriteStream() {
      const stream = new EventEmitter();
      stream.end = () => {};
      return stream;
    },
  };
  const context = {
    require: (name) => name === 'electron' ? electron : name === 'node:fs' ? fakeFs
      : name === 'node:http' ? http : name === 'node:child_process' ? { spawn } : require(name),
    __dirname: path.join(projectRoot, 'desktop'),
    process: {
      platform: 'darwin', env,
      kill(pid, signal) {
        state.signals.push([pid, signal]);
        if (signal === 0 && !state.alive) throw Object.assign(new Error('gone'), { code: 'ESRCH' });
        if (signal === 'SIGTERM') state.alive = false;
      },
    },
    setTimeout, clearTimeout, URL,
  };
  vm.runInNewContext(`${source}\n;globalThis.api = { readStatus, startBackend, requestQuit, createWindow };`, context);
  return { ...context.api, state,
    connectionRefused() { state.firstError = Object.assign(new Error('refused'), { code: 'ECONNREFUSED' }); } };
}

test('existing services require the current protocol and the same project/data', async (t) => {
  const studio = desktop(t);
  assert.equal((await studio.readStatus()).api_version, 2);
  studio.state.status.api_version = 1;
  await assert.rejects(studio.startBackend(), /eski veya uyumsuz/);
  studio.state.status.api_version = 2;
  studio.state.status.project_root = path.join(os.tmpdir(), 'another-hype-checkout');
  await assert.rejects(studio.startBackend(), /farklı proje veya veri/);
  studio.state.status.project_root = projectRoot;
  studio.state.status.data_dir = path.join(os.tmpdir(), 'another-hype-data');
  await assert.rejects(studio.startBackend(), /farklı proje veya veri/);
  assert.equal(studio.state.spawns.length, 0);
  assert.equal(studio.state.signals.length, 0);
});

test('backend uses project venv despite a base-Python override and owns its process group', async (t) => {
  const studio = desktop(t, { HYPE_PYTHON: '/external/base/python3.12' });
  studio.connectionRefused();
  await studio.startBackend();
  const [executable, args, options] = studio.state.spawns[0];
  assert.equal(executable, path.join(projectRoot, '.venv/bin/python'));
  assert.deepEqual(Array.from(args), ['-m', 'app.server']);
  assert.equal(options.detached, true);
  assert.equal(options.shell, false);
  await studio.requestQuit();
  assert(studio.state.signals.some(([pid, signal]) => pid === -3210 && signal === 'SIGTERM'));
  assert.equal(studio.state.exits, 1);
});

for (const status of ['queued', 'rendering', 'uploading']) {
  test(`${status} projects require explicit quit confirmation`, async (t) => {
    const studio = desktop(t);
    studio.connectionRefused();
    await studio.startBackend();
    studio.state.projects = { items: [{ status }] };
    await studio.requestQuit();
    assert.equal(studio.state.exits, 0);
    assert.equal(studio.state.signals.length, 0);
    assert.equal(studio.state.dialogs[0].defaultId, 0);
    assert.equal(studio.state.dialogs[0].cancelId, 0);
    studio.state.choice = 1;
    await studio.requestQuit();
    assert.equal(studio.state.exits, 1);
    assert(studio.state.signals.some(([pid, signal]) => pid === -3210 && signal === 'SIGTERM'));
  });
}

test('quitting a reused server never signals its process', async (t) => {
  const studio = desktop(t);
  await studio.startBackend();
  studio.state.projects = { items: [{ status: 'uploading' }] };
  studio.state.choice = 1;
  await studio.requestQuit();
  assert.equal(studio.state.spawns.length, 0);
  assert.equal(studio.state.signals.length, 0);
  assert.match(studio.state.dialogs[0].detail, /ayrı başlatılan sunucudaki işlemler devam eder/);
  assert.equal(studio.state.exits, 1);
});

test('closing the Mac window also preserves a busy job when the user cancels', async (t) => {
  const studio = desktop(t);
  studio.createWindow();
  studio.state.projects = { items: [{ status: 'rendering' }] };
  const event = { prevented: false, preventDefault() { this.prevented = true; } };
  studio.state.windows[0].emit('close', event);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(event.prevented, true);
  assert.equal(studio.state.dialogs.length, 1);
  assert.equal(studio.state.exits, 0);
  assert.equal(studio.state.signals.length, 0);
});
