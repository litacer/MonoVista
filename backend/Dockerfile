FROM python:3.10-slim

WORKDIR /app

# 1. 替换 Debian 软件源为阿里云镜像 (解决 apt-get 卡顿)
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources || \
    sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list

# 2. 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 3. 复制 requirements.txt 并使用清华大学镜像源 (解决 pip install 卡顿)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 复制项目文件 (利用 Docker 缓存机制，把经常变动的代码放最后)
COPY . /app

ENV PYTHONUNBUFFERED=1
EXPOSE 5000

# 5. Gunicorn 配置优化
# 注意：2C4G 运行深度学习模型，-w 1 (1个worker) 是明智的，否则内存会爆
CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:5000", "app:app", "--timeout", "300"]