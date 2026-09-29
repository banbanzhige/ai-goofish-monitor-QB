// B3 页面参数和任务作用域回归；不连接真实浏览器或账号。
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { test } = require('node:test');

const api = readFileSync(join(__dirname, '../static/js/modules/api.js'), 'utf8');
const view = readFileSync(join(__dirname, '../static/js/modules/results_view.js'), 'utf8');
function section(source, start, end) {
    const from = source.indexOf(start);
    const to = source.indexOf(end, from);
    assert.ok(from >= 0 && to > from, '生产代码标记改变，需复核测试范围');
    return source.slice(from, to);
}

test('列表与导出共享服务端视图参数', () => {
    const context = vm.createContext({ URLSearchParams });
    vm.runInContext(section(api, 'function resultViewParams(', '\nasync function resultManagementRequest('), context);
    const params = vm.runInContext("resultViewParams('all', true, '任务 A', '无人机', 'all', 'price', 'asc', 'Xbox', true)", context);
    assert.equal(params.get('recommended_only'), 'true');
    assert.equal(params.get('include_hidden'), 'true');
    assert.equal(params.get('manual_keyword'), 'Xbox');
    assert.equal(params.get('sort_by'), 'price');
});

test('黑名单默认任务作用域，个人全局须明确勾选', () => {
    const fields = { 'result-file-selector': { value: '任务_A_full_data.jsonl' },
        'blacklist-global': { checked: false }, 'blacklist-kind': { value: 'keyword' },
        'blacklist-pattern': { value: '无人机' } };
    const context = vm.createContext({
        resultViewTasks: [{ task_name: '任务 A', stable_task_id: '82b6e47e-750d-4cc8-bfd0-b45a9be87011' }],
        document: { getElementById: id => fields[id] }
    });
    vm.runInContext(section(view, 'function resultTaskRef(', '\nasync function saveResultViewPreference('), context);
    vm.runInContext(section(view, 'function resultRulePayload(', '\nasync function fetchAndRenderResults('), context);
    const taskPayload = vm.runInContext('resultRulePayload()', context);
    assert.equal(taskPayload.scope, 'task');
    assert.equal(taskPayload.task_ref, '82b6e47e-750d-4cc8-bfd0-b45a9be87011');
    fields['blacklist-global'].checked = true;
    const globalPayload = vm.runInContext('resultRulePayload()', context);
    assert.equal(globalPayload.scope, 'global');
    assert.equal(globalPayload.task_ref, null);
    fields['blacklist-global'].checked = false;
    fields['result-file-selector'].value = 'all';
    assert.throws(() => vm.runInContext('resultRulePayload()', context), /具体任务/);
});

test('旧浏览器文件键不再被读取', () => {
    assert.ok(view.includes("localStorage.removeItem('lastSelectedResultFile')"));
    assert.ok(!view.includes("localStorage.getItem('lastSelectedResultFile')"));
});
