// B4 结果卡片与入口的轻量回归；不使用真实账号或浏览器状态。
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { test } = require('node:test');

const render = readFileSync(join(__dirname, '../static/js/modules/render.js'), 'utf8');
const view = readFileSync(join(__dirname, '../static/js/modules/results_view.js'), 'utf8');
const templates = readFileSync(join(__dirname, '../static/js/modules/templates.js'), 'utf8');
const from = render.indexOf('function renderResultsGrid(data) {');
const to = render.indexOf('\nfunction isMobileLayout()', from);
assert.ok(from >= 0 && to > from, '结果渲染函数位置变化，需复核测试');

function renderCard(priceObservation, status = 'ok') {
    const document = {
        getElementById: () => ({ value: '' }),
        querySelectorAll: () => [],
        createElement: () => ({
            set textContent(value) { this.html = String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;'); },
            get innerHTML() { return this.html || ''; }
        })
    };
    const context = vm.createContext({ document, console });
    vm.runInContext(render.slice(from, to), context);
    return vm.runInContext('renderResultsGrid', context)({
        items: [{ 任务名称: '任务 A', 商品信息: { 商品ID: '123', 商品链接: 'https://example.test/?id=123',
            商品标题: 'Xbox 主机', 当前售价: '¥100' }, price_observation: priceObservation,
            price_task_ref: '82b6e47e-750d-4cc8-bfd0-b45a9be87011' }],
        tasks: [{ task_name: '任务 A' }], price_observation_status: status
    });
}

test('卡片显示历史低价与变动，保持原 AI 推荐区独立', () => {
    const html = renderCard({ observation_count: 2, currency: 'CNY', lowest_amount: '80.00',
        change_amount: '-20.00' });
    assert.match(html, /历史低价 CNY 80\.00/);
    assert.match(html, /较上次下降 20\.00/);
    assert.match(html, /AI建议/);
    assert.match(html, /data-task-ref="82b6e47e-750d-4cc8-bfd0-b45a9be87011"/);
});

test('无观察及不可用状态明确，不把缺测显示为零', () => {
    assert.match(renderCard({ observation_count: 0 }), /暂无观察/);
    assert.match(renderCard({}, 'unavailable'), /价格历史暂不可用/);
    assert.doesNotMatch(renderCard({ observation_count: 0 }), /历史低价 CNY 0/);
});

test('价格历史留在结果页，不新增导航或第二套评分', () => {
    assert.match(templates, /id="results-price-stats"/);
    assert.match(templates, /id="price-history-dialog"/);
    assert.match(view, /\/api\/price-observations\/export\.csv/);
    assert.match(view, /\/api\/price-observations\/items\//);
    assert.doesNotMatch(render, /value_score|deal_score/);
});
