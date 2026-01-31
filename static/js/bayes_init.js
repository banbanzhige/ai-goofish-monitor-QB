/**
 * 初始化Bayes可视化管理器
 * 当Bayes管理tab被点击时自动加载
 */
(function () {
    let bayesManager = null;
    let initializing = false;
    let lastInitializedContainer = null;

    async function ensureBayesManagerInitialized() {
        const container = document.getElementById('bayes-cards-container');
        if (!container || initializing) {
            return;
        }

        // 检查是否是同一个容器元素，如果容器被重新渲染则需要重新初始化
        if (container === lastInitializedContainer && container.dataset.bayesInitialized === 'true') {
            console.log('Bayes manager already initialized for this container');
            return;
        }

        if (typeof BayesVisualManager === 'undefined') {
            console.error('BayesVisualManager class not found');
            return;
        }

        initializing = true;
        try {
            console.log('Initializing Bayes visual manager...');
            bayesManager = new BayesVisualManager();
            window.bayesManager = bayesManager;
            await bayesManager.initialize();
            container.dataset.bayesInitialized = 'true';
            lastInitializedContainer = container;
            console.log('Bayes visual manager initialized successfully');
        } catch (error) {
            console.error('Failed to initialize Bayes manager:', error);
            if (container) {
                container.innerHTML = `
                    <div class="error-message">
                        <p>❌ 初始化失败: ${error.message}</p>
                        <button onclick="location.reload()" class="control-button">刷新页面</button>
                    </div>
                `;
            }
        } finally {
            initializing = false;
        }
    }

    window.ensureBayesManagerInitialized = ensureBayesManagerInitialized;

    document.addEventListener('click', (event) => {
        const tab = event.target.closest('[data-tab="settings-tab-bayes"]');
        if (!tab) {
            return;
        }
        ensureBayesManagerInitialized();
    });

    document.addEventListener('bayes-tab-activated', () => {
        ensureBayesManagerInitialized();
    });
})();
