import { build } from '../../frontend/node_modules/esbuild/lib/main.js';
import Module from 'node:module';
import path from 'node:path';
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const thisFile = fileURLToPath(import.meta.url);
const root = path.resolve(path.dirname(thisFile), '../..');
const entry = path.join(path.dirname(thisFile), 'media_workspace.test.tsx');
const output = await build({
  entryPoints: [entry], bundle: true, write: false, platform: 'node', format: 'cjs',
  packages: 'external', jsx: 'automatic', logLevel: 'silent',
});
const testModule = new Module(path.join(root, 'frontend', '__media_workspace_tests__.cjs'));
testModule.filename = path.join(root, 'frontend', '__media_workspace_tests__.cjs');
testModule.paths = Module._nodeModulePaths(path.join(root, 'frontend'));
testModule._compile(output.outputFiles[0].text, testModule.filename);
console.log(testModule.exports.runMediaWorkspaceTests());

// Phase 6 dashboard contract checks: ensure analytics filters/charts and
// persisted ANPR/alert workflows remain wired into their existing pages.
const readPage = (name) => fs.readFileSync(path.join(root, 'frontend', 'src', 'pages', name), 'utf8');
const analytics = readPage('Analytics.tsx');
assert.match(analytics, /Analytics start date/);
assert.match(analytics, /Analytics camera/);
assert.match(analytics, /Traffic trend interval/);
assert.match(analytics, /data\.time_series/);
assert.match(analytics, /vehicle_confidence_distribution/);
assert.match(analytics, /plate_confidence_distribution/);
assert.match(analytics, /ocr_confidence_distribution/);
const vehicles = readPage('Vehicles.tsx');
assert.match(vehicles, /searchANPRHistory/);
assert.match(vehicles, /raw_ocr_text/);
assert.match(vehicles, /validated_registration_number/);
const alerts = readPage('Alerts.tsx');
assert.match(alerts, /getAlertsPage/);
assert.match(alerts, /acknowledgeAlert/);
assert.match(alerts, /resolveAlert/);
assert.match(alerts, /createAlertRule/);
assert.match(alerts, /updateAlertRule/);
console.log('Phase 6 frontend dashboard contracts passed (analytics filters/charts, real ANPR history, alert management).');

const appSource = fs.readFileSync(path.join(root, 'frontend', 'src', 'App.tsx'), 'utf8');
assert.match(appSource, /import\.meta\.env\?\.DEV === true && import\.meta\.env\?\.VITE_DEV_AUTH_BYPASS === 'true'/);
assert.match(appSource, /if\(DEV_AUTH_BYPASS\)\{setUser\(developmentUser\);setChecking\(false\);/);
const apiSource = fs.readFileSync(path.join(root, 'frontend', 'src', 'services', 'api.ts'), 'utf8');
assert.match(apiSource, /!DEV_AUTH_BYPASS && error\?\.response\?\.status === 401/);
console.log('Development auth bypass frontend route and API guard checks passed.');
