// After the suite finishes, purge the PWTEST cases it created from bank.db so
// the demo queue stays clean. Uses the project's venv310 Python.
const { execFileSync } = require('child_process');
const path = require('path');
const fs = require('fs');

module.exports = async () => {
  const root = path.resolve(__dirname, '..', '..');
  const py = path.join(root, 'venv310', 'Scripts', 'python.exe');
  const script = path.join(__dirname, 'cleanup.py');
  const exe = fs.existsSync(py) ? py : 'python';
  try {
    const out = execFileSync(exe, [script], { encoding: 'utf-8' });
    console.log(out.trim());
  } catch (e) {
    console.log('[cleanup] teardown skipped:', e.message);
  }
};
