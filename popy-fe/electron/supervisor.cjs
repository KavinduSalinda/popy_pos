const { app } = require('electron');
const { spawn } = require('child_process');
const crypto = require('crypto');
const fs = require('fs');
const net = require('net');
const path = require('path');

const MYSQL_PORT_START = 3307;
const API_PORT_START = 18765;

let mysqlProc = null;
let djangoProc = null;
let logStream = null;
let logBuffer = '';
let stopping = false;

function dataDir() {
  const base = process.env.LOCALAPPDATA || app.getPath('userData');
  return path.join(base, 'Popy POS');
}

function runtimeRoot() {
  if (app.isPackaged) return process.resourcesPath;
  return path.resolve(__dirname, '../../desktop/runtime');
}

function frontendDist() {
  if (app.isPackaged) return path.join(process.resourcesPath, 'app', 'dist');
  return path.resolve(__dirname, '../dist');
}

function mysqlPath(value) {
  return value.replace(/\\/g, '/');
}

function quoteIni(value) {
  return `"${mysqlPath(value)}"`;
}

function log(chunk) {
  const text = String(chunk);
  logBuffer = (logBuffer + text).slice(-8000);
  if (logStream) logStream.write(text);
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function readConfig(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return {};
  }
}

function writeConfig(file, config) {
  fs.writeFileSync(file, JSON.stringify(config, null, 2));
}

function canListen(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once('error', () => resolve(false));
    server.once('listening', () => server.close(() => resolve(true)));
    server.listen(port, '127.0.0.1');
  });
}

async function waitUntilFree(port, timeoutMs) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (await canListen(port)) return true;
    await new Promise((resolve) => setTimeout(resolve, 400));
  }
  return false;
}

async function findFreePort(start) {
  for (let port = start; port < start + 40; port += 1) {
    if (port === 3306) continue;
    if (await canListen(port)) return port;
  }
  throw new Error(`No free local port from ${start}.`);
}

function runProcess(exe, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(exe, args, { windowsHide: true });
    let output = '';
    child.stdout?.on('data', (chunk) => {
      output += chunk;
      log(chunk);
    });
    child.stderr?.on('data', (chunk) => {
      output += chunk;
      log(chunk);
    });
    child.on('error', reject);
    child.on('exit', (code) => {
      if (code === 0) resolve(output);
      else {
        reject(
          new Error(
            `${path.basename(exe)} exited with code ${code}.\n${output.slice(-2000)}`,
          ),
        );
      }
    });
  });
}

function waitForPort(port, timeoutMs) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const socket = net.connect({ host: '127.0.0.1', port }, () => {
        socket.end();
        resolve();
      });
      socket.on('error', () => {
        socket.destroy();
        if (Date.now() - started > timeoutMs) {
          reject(new Error(`Timed out waiting for port ${port}.`));
          return;
        }
        setTimeout(attempt, 400);
      });
    };
    attempt();
  });
}

async function waitForHealth(port, timeoutMs) {
  const started = Date.now();
  const url = `http://127.0.0.1:${port}/api/health`;
  while (Date.now() - started < timeoutMs) {
    if (djangoProc && djangoProc.exitCode != null) {
      throw new Error(`The local server stopped.\n${logBuffer.slice(-2000)}`);
    }
    try {
      const response = await fetch(url);
      if (response.ok) {
        const body = await response.json();
        if (body.database === 'up') return body;
      }
    } catch {
      /* server still starting */
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`The local server did not become ready.\n${logBuffer.slice(-2000)}`);
}

function writeMysqlFiles(paths, config, includeInit) {
  const ini = [
    '[mysqld]',
    `basedir=${quoteIni(paths.mysqlHome)}`,
    `datadir=${quoteIni(paths.mysqlData)}`,
    `tmpdir=${quoteIni(paths.tmpDir)}`,
    `port=${config.mysqlPort}`,
    'bind-address=127.0.0.1',
    'mysqlx=0',
    `pid-file=${quoteIni(paths.pidFile)}`,
    `log-error=${quoteIni(paths.errorLog)}`,
    'character-set-server=utf8mb4',
    'collation-server=utf8mb4_unicode_ci',
    'innodb_buffer_pool_size=128M',
    '',
  ].join('\n');
  fs.writeFileSync(paths.iniFile, ini);

  const client = [
    '[client]',
    'user=root',
    `password=${config.password}`,
    'host=127.0.0.1',
    `port=${config.mysqlPort}`,
    'protocol=TCP',
    '',
  ].join('\n');
  fs.writeFileSync(paths.clientFile, client);

  if (!includeInit) return;
  const sql = [
    `ALTER USER 'root'@'localhost' IDENTIFIED BY '${config.password}';`,
    `CREATE USER IF NOT EXISTS 'root'@'127.0.0.1' IDENTIFIED BY '${config.password}';`,
    "GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION;",
    'CREATE DATABASE IF NOT EXISTS popy CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;',
    `CREATE USER IF NOT EXISTS 'popy'@'127.0.0.1' IDENTIFIED BY '${config.password}';`,
    "GRANT ALL PRIVILEGES ON popy.* TO 'popy'@'127.0.0.1';",
    'FLUSH PRIVILEGES;',
    '',
  ].join('\n');
  fs.writeFileSync(paths.initFile, sql);
}

function pathsFor(root) {
  const dir = dataDir();
  return {
    dir,
    configFile: path.join(dir, 'config.json'),
    mysqlData: path.join(dir, 'mysql-data'),
    media: path.join(dir, 'media'),
    staticRoot: path.join(dir, 'staticfiles'),
    logs: path.join(dir, 'logs'),
    tmpDir: path.join(dir, 'tmp'),
    iniFile: path.join(dir, 'my.ini'),
    clientFile: path.join(dir, 'client.cnf'),
    initFile: path.join(dir, 'bootstrap.sql'),
    readyFile: path.join(dir, 'mysql-ready'),
    pidFile: path.join(dir, 'mysql.pid'),
    errorLog: path.join(dir, 'logs', 'mysql.err'),
    desktopLog: path.join(dir, 'logs', 'desktop.log'),
    mysqlHome: path.join(root, 'mysql'),
    mysqld: path.join(root, 'mysql', 'bin', 'mysqld.exe'),
    mysqladmin: path.join(root, 'mysql', 'bin', 'mysqladmin.exe'),
    python: path.join(root, 'python', 'python.exe'),
    backend: path.join(root, 'backend'),
    frontend: frontendDist(),
  };
}

async function ensureMysql(paths, config) {
  ensureDir(paths.mysqlData);
  ensureDir(paths.tmpDir);
  const initialized = fs.existsSync(path.join(paths.mysqlData, 'mysql'));
  if (!initialized) {
    log('Initializing private MySQL data directory.\n');
    await runProcess(paths.mysqld, [
      '--no-defaults',
      `--basedir=${paths.mysqlHome}`,
      `--datadir=${paths.mysqlData}`,
      '--initialize-insecure',
      '--console',
    ]);
  }
  const firstBoot = !fs.existsSync(paths.readyFile);
  writeMysqlFiles(paths, config, firstBoot);
  const args = [
    `--defaults-file=${paths.iniFile}`,
    `--basedir=${paths.mysqlHome}`,
    '--console',
  ];
  if (firstBoot) args.push(`--init-file=${paths.initFile}`);
  mysqlProc = spawn(paths.mysqld, args, { windowsHide: true });
  mysqlProc.stdout?.on('data', log);
  mysqlProc.stderr?.on('data', log);
  mysqlProc.on('exit', (code) => {
    if (!stopping) log(`mysqld exited with code ${code}\n`);
  });
  await waitForPort(config.mysqlPort, firstBoot ? 120000 : 45000);
  if (firstBoot) {
    fs.writeFileSync(paths.readyFile, 'ok');
    fs.rmSync(paths.initFile, { force: true });
  }
}

function startDjango(paths, config) {
  const env = {
    ...process.env,
    DJANGO_SETTINGS_MODULE: 'config.settings.desktop',
    POPY_ENABLE_DESKTOP_SETUP: '1',
    SECRET_KEY: config.secretKey,
    DB_NAME: 'popy',
    DB_USER: 'popy',
    DB_PASSWORD: config.password,
    DB_HOST: '127.0.0.1',
    DB_PORT: String(config.mysqlPort),
    POPY_MEDIA_ROOT: paths.media,
    POPY_STATIC_ROOT: paths.staticRoot,
    POPY_FRONTEND_DIST: paths.frontend,
    POPY_BIND_HOST: '127.0.0.1',
    POPY_BIND_PORT: String(config.apiPort),
    PYTHONUTF8: '1',
    PYTHONIOENCODING: 'utf-8',
    PYTHONDONTWRITEBYTECODE: '1',
  };
  djangoProc = spawn(paths.python, ['desktop_entry.py'], {
    cwd: paths.backend,
    env,
    windowsHide: true,
  });
  djangoProc.stdout?.on('data', log);
  djangoProc.stderr?.on('data', log);
  djangoProc.on('exit', (code) => {
    if (!stopping) log(`Django exited with code ${code}\n`);
  });
}

async function startStack() {
  const root = runtimeRoot();
  const paths = pathsFor(root);
  for (const dir of [paths.dir, paths.logs, paths.media, paths.staticRoot, paths.tmpDir]) {
    ensureDir(dir);
  }
  logStream = fs.createWriteStream(paths.desktopLog, { flags: 'a' });
  if (!fs.existsSync(paths.mysqld) || !fs.existsSync(paths.python)) {
    throw new Error(
      'The private MySQL runtime is not in this build. Run desktop/fetch-runtime.ps1 before packaging.',
    );
  }
  if (!fs.existsSync(path.join(paths.frontend, 'index.html'))) {
    throw new Error('The POS interface build is missing from this installation.');
  }

  const saved = readConfig(paths.configFile);
  const config = {
    mysqlPort: saved.mysqlPort || (await findFreePort(MYSQL_PORT_START)),
    apiPort: saved.apiPort || (await findFreePort(API_PORT_START)),
    password: saved.password || crypto.randomBytes(24).toString('hex'),
    secretKey: saved.secretKey || crypto.randomBytes(32).toString('hex'),
  };
  if (config.mysqlPort === 3306) config.mysqlPort = await findFreePort(MYSQL_PORT_START);
  const dataReady = fs.existsSync(path.join(paths.mysqlData, 'mysql'));
  if (!(await canListen(config.mysqlPort))) {
    if (dataReady) {
      writeMysqlFiles(paths, config, false);
      await shutdownMysql(paths);
      const freed = await waitUntilFree(config.mysqlPort, 8000);
      if (!freed) {
        throw new Error(
          `Private MySQL is still running on port ${config.mysqlPort}. End mysqld.exe and open Popy again.`,
        );
      }
    } else {
      config.mysqlPort = await findFreePort(MYSQL_PORT_START);
    }
  }
  if (!(await canListen(config.apiPort)) || config.apiPort === config.mysqlPort) {
    config.apiPort = await findFreePort(API_PORT_START);
  }
  writeConfig(paths.configFile, config);

  await ensureMysql(paths, config);
  startDjango(paths, config);
  await waitForHealth(config.apiPort, 180000);
  return { apiUrl: `http://127.0.0.1:${config.apiPort}` };
}

function waitExit(child, timeoutMs) {
  if (!child || child.exitCode != null) return Promise.resolve();
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve(), timeoutMs);
    child.once('exit', () => {
      clearTimeout(timer);
      resolve();
    });
  });
}

async function shutdownMysql(paths) {
  if (paths && fs.existsSync(paths.mysqladmin) && fs.existsSync(paths.clientFile)) {
    const admin = spawn(paths.mysqladmin, [`--defaults-file=${paths.clientFile}`, 'shutdown'], {
      windowsHide: true,
    });
    await waitExit(admin, 15000);
  }
  if (mysqlProc && mysqlProc.exitCode == null) {
    mysqlProc.kill();
    await waitExit(mysqlProc, 5000);
  }
}

async function stopStack() {
  if (stopping) return;
  stopping = true;
  const paths = pathsFor(runtimeRoot());
  if (djangoProc && djangoProc.exitCode == null) {
    djangoProc.kill();
    await waitExit(djangoProc, 8000);
  }
  await shutdownMysql(paths);
  if (logStream) logStream.end();
}

module.exports = { startStack, stopStack };
