// Chrome扩展的弹出页脚本
document.addEventListener('DOMContentLoaded', function() {
  const extractBtn = document.getElementById('extractBtn');
  const copyBtn = document.getElementById('copyBtn');
  const stateOutput = document.getElementById('stateOutput');
  const statusDiv = document.getElementById('status');

  // 更新状态消息
  function updateStatus(message, isSuccess = false) {
    statusDiv.textContent = message;
    statusDiv.className = 'status ' + (isSuccess ? 'success' : 'error');
    setTimeout(() => {
      statusDiv.textContent = '';
      statusDiv.className = 'status';
    }, 3000);
  }

  // 将Chrome cookie的sameSite值映射为Playwright兼容的值
  function mapSameSiteValue(chromeSameSite) {
    // Chrome对于没有SameSite属性的cookie返回undefined
    if (chromeSameSite === undefined || chromeSameSite === null) {
      return "Lax"; // 未指定cookie的默认值
    }
    
    // 将Chrome的cookie sameSite值映射为Playwright期望的值（带正确的大小写）
    const sameSiteMap = {
      "no_restriction": "None",
      "lax": "Lax",
      "strict": "Strict",
      "unspecified": "Lax" // 将未指定的视为Lax（浏览器默认值）
    };
    
    return sameSiteMap[chromeSameSite] || "Lax";
  }

  // 点击按钮时提取cookie
  extractBtn.addEventListener('click', async () => {
    try {
      const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
      
      if (!tab.url.includes('goofish.com')) {
        updateStatus('请先导航到goofish.com网站');
        return;
      }

      // 从弹出页脚本直接调用chrome.cookies API
      const cookies = await new Promise((resolve) => {
        chrome.cookies.getAll({url: "https://www.goofish.com/"}, resolve);
      });
      
      const state = {
        cookies: cookies.map(cookie => ({
          name: cookie.name,
          value: cookie.value,
          domain: cookie.domain,
          path: cookie.path,
          expires: cookie.expirationDate,
          httpOnly: cookie.httpOnly,
          secure: cookie.secure,
          sameSite: mapSameSiteValue(cookie.sameSite)
        }))
      };

      stateOutput.value = JSON.stringify(state, null, 2);
      updateStatus('登录状态提取成功！', true);
    } catch (error) {
      console.error('提取cookie错误:', error);
      updateStatus('错误: ' + error.message);
    }
  });

  // 点击按钮时复制到剪贴板
  copyBtn.addEventListener('click', () => {
    if (stateOutput.value) {
      navigator.clipboard.writeText(stateOutput.value)
        .then(() => {
          updateStatus('已复制到剪贴板！', true);
        })
        .catch(err => {
          updateStatus('复制失败: ' + err);
        });
    } else {
      updateStatus('没有数据可复制');
    }
  });
});
