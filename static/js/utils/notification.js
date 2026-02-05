/**
 * 通知工具类 - 基于 SweetAlert2
 * 统一管理项目中的所有提示、警告和确认对话框
 */

const Notification = {
    /**
     * 成功提示 (Toast 样式,自动消失)
     * @param {string} message - 提示消息
     * @param {string} title - 标题 (可选)
     * @param {number} timer - 自动关闭时间(ms),默认 2000
     */
    success(message, title = '成功', timer = 2000) {
        return Swal.fire({
            icon: 'success',
            title: title,
            text: message,
            timer: timer,
            showConfirmButton: false,
            toast: true,
            position: 'top-end',
            timerProgressBar: true,
            customClass: {
                popup: 'colored-toast'
            }
        });
    },

    /**
     * 成功提示 (对话框样式,需要确认)
     * @param {string} message - 提示消息
     * @param {string} title - 标题 (可选)
     */
    successDialog(message, title = '成功') {
        return Swal.fire({
            icon: 'success',
            title: title,
            text: message,
            confirmButtonText: '确定',
            confirmButtonColor: '#52c41a'
        });
    },

    /**
     * 错误提示
     * @param {string} message - 错误消息
     * @param {string} title - 标题 (可选)
     */
    error(message, title = '错误') {
        return Swal.fire({
            icon: 'error',
            title: title,
            text: message,
            confirmButtonText: '确定',
            confirmButtonColor: '#ff4d4f'
        });
    },

    /**
     * 警告提示
     * @param {string} message - 警告消息
     * @param {string} title - 标题 (可选)
     */
    warning(message, title = '警告') {
        return Swal.fire({
            icon: 'warning',
            title: title,
            text: message,
            confirmButtonText: '确定',
            confirmButtonColor: '#faad14'
        });
    },

    /**
     * 信息提示
     * @param {string} message - 信息内容
     * @param {string} title - 标题 (可选)
     */
    info(message, title = '提示') {
        return Swal.fire({
            icon: 'info',
            title: title,
            text: message,
            confirmButtonText: '确定',
            confirmButtonColor: '#1890ff'
        });
    },

    infoMultiline(message, title = '提示') {
        const safeMessage = String(message)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
        return Swal.fire({
            icon: 'info',
            title: title,
            html: safeMessage.replace(/\n/g, '<br>'),
            confirmButtonText: '确定',
            confirmButtonColor: '#1890ff'
        });
    },

    /**
     * 输入对话框
     * @param {string} message - 输入提示
     * @param {object} options - 选项
     * @returns {Promise} - 返回 Promise,result.value 为输入值
     */
    input(message, options = {}) {
        const {
            title = '请输入内容',
            defaultValue = '',
            placeholder = '',
            confirmButtonText = '确定',
            cancelButtonText = '取消'
        } = options;
        return Swal.fire({
            title: title,
            text: message,
            input: 'text',
            inputValue: defaultValue,
            inputPlaceholder: placeholder,
            showCancelButton: true,
            confirmButtonText: confirmButtonText,
            cancelButtonText: cancelButtonText,
            confirmButtonColor: '#1890ff',
            cancelButtonColor: '#d9d9d9',
            reverseButtons: true,
            focusCancel: true
        });
    },

    /**
     * 通用确认对话框
     * @param {string} message - 确认消息
     * @param {string} title - 标题 (可选)
     * @param {object} options - 额外选项
     * @returns {Promise} - 返回 Promise,result.isConfirmed 表示用户是否确认
     */
    confirm(message, title = '确认操作', options = {}) {
        const defaultOptions = {
            title: title,
            text: message,
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            confirmButtonColor: '#1890ff',
            cancelButtonColor: '#d9d9d9',
            reverseButtons: true,
            focusCancel: true
        };

        return Swal.fire({ ...defaultOptions, ...options });
    },

    /**
     * 删除确认对话框 (危险操作)
     * @param {string} message - 确认消息
     * @param {string} title - 标题 (可选)
     * @returns {Promise} - 返回 Promise,result.isConfirmed 表示用户是否确认
     */
    confirmDelete(message, title = '确定删除?') {
        return Swal.fire({
            title: title,
            html: `<p>${message}</p><p style="color: #ff4d4f; font-weight: 600;">此操作不可恢复！</p>`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonText: '确定删除',
            cancelButtonText: '取消',
            confirmButtonColor: '#ff4d4f',
            cancelButtonColor: '#d9d9d9',
            reverseButtons: true,
            focusCancel: true
        });
    },

    /**
     * 加载提示 (无按钮,需要手动关闭)
     * @param {string} message - 加载消息
     * @param {string} title - 标题 (可选)
     */
    loading(message = '加载中...', title = '') {
        return Swal.fire({
            title: title,
            text: message,
            allowOutsideClick: false,
            allowEscapeKey: false,
            showConfirmButton: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });
    },

    /**
     * 关闭当前弹窗
     */
    close() {
        Swal.close();
    },

    /**
     * Toast 提示 (轻量级,右上角)
     * @param {string} message - 消息内容
     * @param {string} icon - 图标类型: success, error, warning, info
     * @param {number} timer - 自动关闭时间(ms)
     */
    toast(message, icon = 'info', timer = 2000) {
        return Swal.fire({
            toast: true,
            position: 'top-end',
            icon: icon,
            title: message,
            showConfirmButton: false,
            timer: timer,
            timerProgressBar: true,
            didOpen: (toast) => {
                toast.addEventListener('mouseenter', Swal.stopTimer);
                toast.addEventListener('mouseleave', Swal.resumeTimer);
            }
        });
    }
};

// 导出到全局作用域供其他模块使用
window.Notification = Notification;

// 为了向后兼容,保留一个简化的 alert 替代方法
window.showAlert = function (message) {
    console.warn('showAlert is deprecated, please use Notification.toast or Notification.success instead');
    Notification.toast(message, 'info');
};

// 为了向后兼容,保留一个简化的 confirm 替代方法
window.showConfirm = async function (message) {
    console.warn('showConfirm is deprecated, please use Notification.confirm instead');
    const result = await Notification.confirm(message);
    return result.isConfirmed;
};
