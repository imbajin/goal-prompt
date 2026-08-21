#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');

function arg(name) {
  const index = process.argv.indexOf(name);
  if (index < 0 || index + 1 >= process.argv.length) {
    throw new Error(`missing ${name}`);
  }
  return process.argv[index + 1];
}

function loadPlaywright() {
  try {
    return require('playwright');
  } catch (_) {
    return require('/opt/hg-ab/node_modules/playwright');
  }
}

async function payload(response, name, accepted = [200]) {
  const body = await response.json().catch(() => null);
  if (!response.ok() || !body || !accepted.includes(body.status)) {
    throw new Error(`${name} failed HTTP=${response.status()} body=${JSON.stringify(body)}`);
  }
  return body.data;
}

async function setupSchema(request, hubbleUrl) {
  const base = `${hubbleUrl}/api/v1.3/graphspaces/DEFAULT/graphs/hugegraph/schema`;
  for (const name of ['name', 'description']) {
    await payload(await request.post(`${base}/propertykeys`, {
      data: {name, data_type: 'TEXT', cardinality: 'SINGLE'}
    }), `propertykey ${name}`);
  }
  await payload(await request.post(`${base}/vertexlabels`, {data: {
    name: 'person',
    id_strategy: 'PRIMARY_KEY',
    properties: [
      {name: 'name', nullable: false},
      {name: 'description', nullable: true}
    ],
    primary_keys: ['name'],
    property_indexes: [],
    open_label_index: true,
    style: {color: '#2B65FF', icon: 'user', display_fields: ['name']}
  }}), 'vertexlabel person');
}

async function authenticate(context, page, hubbleUrl, password) {
  const user = await payload(await context.request.post(`${hubbleUrl}/api/v1.3/auth/login`, {
    data: {user_name: 'admin', user_password: password}
  }), 'hubble login');
  const status = await payload(await context.request.get(`${hubbleUrl}/api/v1.3/auth/status`), 'auth status');
  const config = await payload(await context.request.get(`${hubbleUrl}/api/v1.3/config`), 'config');
  await page.addInitScript(session => {
    window.localStorage.setItem('languageType', 'en-US');
    window.sessionStorage.setItem('user_', JSON.stringify(session.user));
    window.sessionStorage.setItem('hubble_config_', JSON.stringify(session.config));
  }, {user, config});
  if (!status.level) {
    throw new Error('auth status has no level');
  }
}

function isExpectedApi(url, suffix) {
  try {
    return new URL(url).pathname === `/api/v1.3/graphspaces/DEFAULT/graphs/hugegraph/${suffix}`;
  } catch (_) {
    return false;
  }
}

async function choosePerson(page) {
  const drawer = page.locator('.ant-drawer').filter({hasText: /Add Vertex|新增顶点/}).last();
  await drawer.locator('.ant-select-selector').click();
  await page.getByRole('option', {name: 'person'}).click();
  return drawer;
}

async function field(drawer, name) {
  const item = drawer.locator('.ant-form-item').filter({hasText: new RegExp(`^\\s*${name}\\b`, 'i')});
  const input = item.locator('input').first();
  await input.waitFor({state: 'visible'});
  return input;
}

async function openNewVertex(page) {
  await page.getByRole('button', {name: /New|新建/}).click();
  const addVertex = page.getByText(/Add Vertex|新增顶点/, {exact: true}).last();
  await addVertex.waitFor({state: 'visible'});
  const edgeItems = [
    page.getByText(/Add In Edge|新增入边/, {exact: true}).last(),
    page.getByText(/Add Out Edge|新增出边/, {exact: true}).last()
  ];
  let edgesDisabled = true;
  for (const item of edgeItems) {
    if (await item.count() === 0) continue;
    const menu = item.locator('xpath=ancestor::*[@role="menuitem"][1]');
    const disabled = await menu.getAttribute('aria-disabled');
    edgesDisabled = edgesDisabled && (disabled === 'true' || await menu.evaluate(node => (
      node.classList.contains('ant-dropdown-menu-item-disabled') || node.hasAttribute('disabled')
    )));
  }
  await addVertex.click();
  return edgesDisabled;
}

async function executeEmptyQuery(page, hubbleUrl) {
  await page.goto(`${hubbleUrl}/gremlin/DEFAULT/hugegraph`, {waitUntil: 'domcontentloaded'});
  const editor = page.locator('.cm-content[contenteditable="true"]').first();
  await editor.waitFor({state: 'visible', timeout: 30000});
  await editor.fill("g.V().hasLabel('person')");
  const responsePromise = page.waitForResponse(response => (
    isExpectedApi(response.url(), 'gremlin-query') && response.request().method() === 'POST'
  ));
  await page.getByRole('button', {name: /Run Query|执行查询/}).click();
  const response = await responsePromise;
  const body = await response.json();
  if (!response.ok() || body.status !== 200) {
    throw new Error(`empty query failed: ${JSON.stringify(body)}`);
  }
  await page.getByRole('group', {name: /Nodes: 0 in this result|节点：当前结果 0/})
    .waitFor({state: 'visible'});
  await page.locator('canvas').last().waitFor({state: 'visible'});
  await page.getByRole('button', {name: /New|新建/}).waitFor({state: 'visible'});
}

async function persistedDescription(context, hubbleUrl) {
  const response = await context.request.post(
    `${hubbleUrl}/api/v1.3/graphspaces/DEFAULT/graphs/hugegraph/gremlin-query`,
    {data: {content: "g.V().hasLabel('person').has('name','alice').valueMap(true)"}}
  );
  const data = await payload(response, 'persistence query');
  return JSON.stringify(data).includes('first vertex');
}

async function main() {
  const workspace = path.resolve(arg('--workspace'));
  const output = path.resolve(arg('--output'));
  const evidence = path.dirname(output);
  const password = process.env.HG_AB_SERVER_PASSWORD;
  if (!password) throw new Error('HG_AB_SERVER_PASSWORD is required');
  fs.mkdirSync(evidence, {recursive: true});
  const report = {
    status: 'failed', new_click: false, canvas_count: false,
    nullable_edit: false, put_persistence: false, failure_state: false,
    api_contract: false, browser_network: false,
    edge_without_endpoints_enabled: null, cross_graph_request: false
  };
  let browser;
  try {
    const {chromium} = loadPlaywright();
    browser = await chromium.launch({headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH});
  } catch (error) {
    report.error = error.stack || String(error);
    report.environment_error = true;
    fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
    process.exit(2);
  }
  try {
    const hubbleUrl = process.env.HG_AB_HUBBLE_URL;
    if (!hubbleUrl) throw new Error('HG_AB_HUBBLE_URL is required');
    const context = await browser.newContext();
    const page = await context.newPage({viewport: {width: 1440, height: 1000}});
    const consoleErrors = [];
    const vertexMutations = [];
    page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
    page.on('request', request => {
      const pathname = new URL(request.url()).pathname;
      if (/\/graphspaces\/[^/]+\/graphs\/[^/]+\/vertex(?:\/|$)/.test(pathname) &&
          ['POST', 'PUT'].includes(request.method())) vertexMutations.push(request);
    });
    await authenticate(context, page, hubbleUrl, password);
    await setupSchema(context.request, hubbleUrl);
    await executeEmptyQuery(page, hubbleUrl);

    const edgeDisabled = await openNewVertex(page);
    report.edge_without_endpoints_enabled = !edgeDisabled;
    const addDrawer = await choosePerson(page);
    const nameInput = await field(addDrawer, 'name');
    const descriptionInput = await field(addDrawer, 'description');
    await nameInput.fill('alice');
    if (await descriptionInput.inputValue() !== '') throw new Error('nullable description was not initially empty');
    const postRequests = [];
    page.on('request', request => {
      if (isExpectedApi(request.url(), 'vertex') && request.method() === 'POST') postRequests.push(request);
    });
    const postResponse = page.waitForResponse(response => isExpectedApi(response.url(), 'vertex') && response.request().method() === 'POST');
    await addDrawer.getByRole('button', {name: /^Add$|^新增$/}).click();
    const posted = await postResponse;
    const postBody = posted.request().postDataJSON();
    report.new_click = posted.ok() && postRequests.length === 1;
    report.api_contract = postBody.label === 'person' && postBody.properties.name === 'alice' && !('description' in postBody.properties);
    const count = page.getByRole('group', {name: /Nodes: 1 in this result|节点：当前结果 1/});
    await count.waitFor({state: 'visible'});
    report.canvas_count = true;

    const canvas = page.locator('canvas').last();
    await canvas.waitFor({state: 'visible'});
    const box = await canvas.boundingBox();
    if (!box) throw new Error('canvas has no box');
    await canvas.click({position: {x: box.width / 2, y: box.height / 2}});
    const editDrawer = page.locator('.ant-drawer').filter({hasText: /Data Details|数据详情/}).last();
    await editDrawer.waitFor({state: 'visible'});
    await editDrawer.getByRole('button', {name: /^Edit$|^编辑$/}).click();
    const editDescription = await field(editDrawer, 'description');
    report.nullable_edit = (await editDescription.inputValue()) === '';
    await editDescription.fill('first vertex');
    const puts = [];
    page.on('request', request => {
      if (/\/vertex\//.test(new URL(request.url()).pathname) && request.method() === 'PUT') puts.push(request);
    });
    const putResponse = page.waitForResponse(response => (
      /\/api\/v1\.3\/graphspaces\/DEFAULT\/graphs\/hugegraph\/vertex\//.test(new URL(response.url()).pathname) &&
      response.request().method() === 'PUT'
    ));
    await editDrawer.getByRole('button', {name: /^Save$|^保存$/}).click();
    const put = await putResponse;
    const putBody = put.request().postDataJSON();
    report.api_contract = report.api_contract && puts.length === 1 && putBody.properties.description === 'first vertex';
    report.put_persistence = put.ok() && await persistedDescription(context, hubbleUrl);

    // A failed PUT must retain the edit state and must not fabricate a saved
    // value.  This is distinct from the create failure below.
    await canvas.click({position: {x: box.width / 2, y: box.height / 2}});
    const failedEditDrawer = page.locator('.ant-drawer').filter({hasText: /Data Details|数据详情/}).last();
    await failedEditDrawer.waitFor({state: 'visible'});
    await failedEditDrawer.getByRole('button', {name: /^Edit$|^编辑$/}).click();
    const failedDescription = await field(failedEditDrawer, 'description');
    await failedDescription.fill('must-not-persist');
    let failedPutCount = 0;
    await page.route('**/api/v1.3/graphspaces/DEFAULT/graphs/hugegraph/vertex/**', async route => {
      if (route.request().method() === 'PUT') {
        failedPutCount++;
        await route.fulfill({status: 500, contentType: 'application/json', body: JSON.stringify({status: 500, message: 'trusted injected PUT failure'})});
      } else await route.continue();
    });
    await failedEditDrawer.getByRole('button', {name: /^Save$|^保存$/}).click();
    await page.waitForTimeout(500);
    const failedPutHeld = await failedEditDrawer.isVisible() &&
      await failedDescription.inputValue() === 'must-not-persist' &&
      await persistedDescription(context, hubbleUrl);
    await page.unroute('**/api/v1.3/graphspaces/DEFAULT/graphs/hugegraph/vertex/**');

    // A failed POST must not create a ghost vertex or close/clear the drawer.
    await openNewVertex(page);
    const failAddDrawer = await choosePerson(page);
    const failName = await field(failAddDrawer, 'name');
    await failName.fill('bob');
    let failedPostCount = 0;
    await page.route('**/api/v1.3/graphspaces/DEFAULT/graphs/hugegraph/vertex', async route => {
      if (route.request().method() === 'POST') {
        failedPostCount++;
        await route.fulfill({status: 500, contentType: 'application/json', body: JSON.stringify({status: 500, message: 'trusted injected failure'})});
      } else await route.continue();
    });
    await failAddDrawer.getByRole('button', {name: /^Add$|^新增$/}).click();
    await page.waitForTimeout(500);
    const failedPostHeld = await failAddDrawer.isVisible() && await failName.inputValue() === 'bob' && await count.isVisible();
    await page.unroute('**/api/v1.3/graphspaces/DEFAULT/graphs/hugegraph/vertex');
    report.failure_state = failedPostCount === 1 && failedPostHeld && failedPutCount === 1 && failedPutHeld;
    report.cross_graph_request = vertexMutations.some(request => {
      const pathname = new URL(request.url()).pathname;
      return !/^\/api\/v1\.3\/graphspaces\/DEFAULT\/graphs\/hugegraph\/vertex(?:\/|$)/.test(pathname);
    });
    const mutationMethods = vertexMutations.map(request => request.method()).sort();
    report.browser_network = report.new_click &&
      JSON.stringify(mutationMethods) === JSON.stringify(['POST', 'POST', 'PUT', 'PUT']) &&
      failedPostCount === 1 && failedPutCount === 1 && !report.cross_graph_request;
    report.status = Object.entries(report).every(([key, value]) => (
      key === 'status' || key === 'edge_without_endpoints_enabled' || key === 'cross_graph_request' ? true : value === true
    )) && report.edge_without_endpoints_enabled === false && report.cross_graph_request === false && consoleErrors.length === 0
      ? 'passed' : 'failed';
    report.console_errors = consoleErrors;
    await page.screenshot({path: path.join(evidence, 'toolchain-final.png'), fullPage: true});
  } catch (error) {
    report.error = error.stack || String(error);
    // Candidate pages and API bodies are untrusted text.  They must never be
    // able to invalidate an arm by printing an infrastructure-looking phrase.
    // Missing reviewed runtime dependencies fail the outer controller before
    // this structured candidate-behavior report is produced.
    report.environment_error = false;
  } finally {
    if (browser) await browser.close().catch(() => {});
    fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
  }
  process.exit(report.environment_error ? 2 : report.status === 'passed' ? 0 : 1);
}

main().catch(error => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exit(2);
});
