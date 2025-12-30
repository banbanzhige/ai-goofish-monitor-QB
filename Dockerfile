# Stage 1: Build the environment with dependencies
FROM python:3.11-slim-bookworm AS builder

# 设置环境变量以防止交互式提示
ENV DEBIAN_FRONTEND=noninteractive

# 创建虚拟环境
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# 安装 Python 依赖到虚拟环境中 (使用国内镜像源加速)
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 只下载 Playwright 的 Chromium 浏览器，系统依赖在下一阶段安装
RUN playwright install chromium

# Stage 2: Create the final, lean image
FROM python:3.11-slim-bookworm

# 设置工作目录和环境变量
WORKDIR /app
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
# 新增环境变量，用于区分Docker环境和本地环境
ENV RUNNING_IN_DOCKER=true
# 告知 Playwright 在哪里找到浏览器
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright
# 设置时区为中国时区
ENV TZ=Asia/Shanghai

# 从 builder 阶段复制虚拟环境，这样我们就可以使用 playwright 命令
COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# 安装所有运行浏览器所需的系统级依赖（包括libzbar0）和网络诊断工具
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tzdata \
        libzbar0 \
        curl \
        wget \
        iputils-ping \
        dnsutils \
        iproute2 \
        netcat-openbsd \
        telnet \
    && playwright install-deps chromium \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 阶段复制预先下载好的浏览器
COPY --from=builder /root/.cache/ms-playwright /root/.cache/ms-playwright

# 复制应用代码
# .dockerignore 文件会处理排除项
COPY . .

# 声明服务运行的端口
EXPOSE 8000

# 容器启动时执行的命令
CMD ["python", "web_server.py"]
