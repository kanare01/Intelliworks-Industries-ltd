import { spawn } from 'child_process';

const flask = spawn('python3', ['app.py'], {
  env: { ...process.env, FLASK_PORT: '5001' },
  stdio: 'inherit'
});

const args = process.argv.slice(2);
const vite = spawn('npx', ['vite', ...args], {
  stdio: 'inherit'
});

function cleanup() {
  try { flask.kill('SIGTERM'); } catch (e) {}
  try { vite.kill('SIGTERM'); } catch (e) {}
  process.exit();
}

process.on('SIGINT', cleanup);
process.on('SIGTERM', cleanup);

flask.on('exit', (code) => {
  if (code !== 0 && code !== null) {
    console.error(`Flask backend exited with code ${code}`);
  }
});

vite.on('exit', (code) => {
  cleanup();
});
