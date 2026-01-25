# 第一阶段：构建依赖环境
FROM python:3.11-slim-bookworm AS builder

# 设置环境变量避免交互式提示
ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
# 告知 Playwright 在哪里找到浏览器
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

# 安装 Python 依赖到临时前缀目录（不使用虚拟环境）
ENV PIP_PREFIX=/install
ENV PYTHONPATH=/install/lib/python3.11/site-packages
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple --prefix=$PIP_PREFIX -r requirements.txt

# 下载 Playwright 的 Chromium 浏览器
RUN python -m playwright install chromium

# 第二阶段：生成最终精简镜像
FROM python:3.11-slim-bookworm

# 设置工作目录和环境变量
WORKDIR /app
ENV PYTHONUNBUFFERED=1
# 新增环境变量，用于区分 Docker 环境和本地环境
ENV RUNNING_IN_DOCKER=true
# 告知 Playwright 在哪里找到浏览器
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright
# 设置时区为中国时区
ENV TZ=Asia/Shanghai

# 复制依赖到系统路径
COPY --from=builder /install /usr/local

# 安装运行浏览器所需的系统级依赖（包含 libzbar0）及网络诊断工具
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
    && python -m playwright install-deps chromium \
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
