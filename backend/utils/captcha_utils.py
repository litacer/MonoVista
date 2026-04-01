"""
captcha_utils.py — 图形验证码生成与 Redis 校验工具

功能说明：
    1. generate_captcha()  — 生成带干扰线/噪点的 4 位随机字母数字图片，
                             以 UUID 为 Key 存入 Redis（TTL 5 分钟），
                             返回 (uuid, base64_image_str)
    2. verify_captcha()    — 从 Redis 校验用户输入，验证通过后立即删除 Key
                             （防止重放攻击）

依赖：
    pip install redis pillow

环境变量（.env）：
    REDIS_HOST   - Redis 主机，默认 localhost
    REDIS_PORT   - Redis 端口，默认 6379
    REDIS_DB     - Redis 数据库编号，默认 0
    REDIS_PWD    - Redis 密码（可选）
"""
import io
import os
import random
import string
import base64
import uuid
from loguru import logger

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    Image = None

try:
    import redis as redis_lib
except ImportError:
    redis_lib = None


# ── Redis 连接（延迟初始化，避免启动时崩溃） ─────────────────────
_redis_client = None


def _get_redis():
    """获取 Redis 客户端单例，配置缺失时抛出 RuntimeError。"""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if redis_lib is None:
        raise RuntimeError("redis-py not installed. Run: pip install redis")
    _redis_client = redis_lib.Redis(
        host     = os.getenv("REDIS_HOST", "localhost"),
        port     = int(os.getenv("REDIS_PORT", 6379)),
        db       = int(os.getenv("REDIS_DB", 1)),
        password = os.getenv("REDIS_PWD", 123456) or None,
        decode_responses = True,   # 返回 str 而非 bytes
        socket_timeout   = 3,
    )
    return _redis_client


# ── 验证码配置常量 ────────────────────────────────────────────────
_CAPTCHA_CHARS  = string.ascii_lowercase + string.digits  # 小写字母 + 数字
_CAPTCHA_LEN    = 4          # 验证码位数
_CAPTCHA_TTL    = 300        # Redis TTL（秒），5 分钟
_IMG_WIDTH      = 160        # 图片宽度（像素）
_IMG_HEIGHT     = 60         # 图片高度（像素）
_NOISE_DOTS     = 80         # 噪点数量
_NOISE_LINES    = 5          # 干扰线数量
_REDIS_PREFIX   = "captcha:" # Redis Key 前缀

# 颜色调色板（深色背景 + 高对比度文字）
_BG_COLORS   = [(8, 12, 20), (14, 20, 32), (10, 16, 28)]
_TEXT_COLORS = [(0, 212, 255), (76, 255, 145), (255, 200, 80), (200, 180, 255)]
_LINE_COLORS = [(30, 60, 90), (20, 50, 80), (40, 70, 100)]


def _draw_captcha_image(text: str) -> str:
    """
    使用 Pillow 绘制验证码图片。

    绘制步骤：
      1. 创建带随机深色背景的 RGB 画布
      2. 绘制干扰线（_NOISE_LINES 条随机折线）
      3. 绘制噪点（_NOISE_DOTS 个随机像素点）
      4. 逐字符绘制文字，每个字符随机旋转 ±20° 并轻微偏移
      5. 应用轻微模糊（SMOOTH_MORE）使图片更自然
      6. 转为 PNG → Base64 字符串返回

    @param text  - 4 位验证码字符串（已转小写）
    @return      - "data:image/png;base64,..." 格式字符串
    """
    if Image is None:
        raise RuntimeError("Pillow not installed. Run: pip install pillow")

    # Step 1：创建画布
    bg_color = random.choice(_BG_COLORS)
    img  = Image.new("RGB", (_IMG_WIDTH, _IMG_HEIGHT), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Step 2：绘制干扰线
    for _ in range(_NOISE_LINES):
        x1 = random.randint(0, _IMG_WIDTH)
        y1 = random.randint(0, _IMG_HEIGHT)
        x2 = random.randint(0, _IMG_WIDTH)
        y2 = random.randint(0, _IMG_HEIGHT)
        color = random.choice(_LINE_COLORS)
        draw.line([(x1, y1), (x2, y2)], fill=color, width=1)

    # Step 3：绘制噪点
    for _ in range(_NOISE_DOTS):
        x = random.randint(0, _IMG_WIDTH - 1)
        y = random.randint(0, _IMG_HEIGHT - 1)
        r = random.randint(20, 80)
        g = random.randint(20, 80)
        b = random.randint(20, 80)
        draw.point((x, y), fill=(r, g, b))

    # Step 4：逐字符绘制文字
    # 每个字符在独立的小画布上绘制后旋转，再粘贴到主画布
    char_w = _IMG_WIDTH // _CAPTCHA_LEN
    try:
        # 尝试加载系统等宽字体；若失败则用 Pillow 内置默认字体
        font = ImageFont.truetype("DejaVuSansMono-Bold.ttf", 32)
    except Exception:
        try:
            font = ImageFont.truetype("cour.ttf", 32)  # Windows Courier New
        except Exception:
            font = ImageFont.load_default()

    for i, ch in enumerate(text):
        # 为每个字符创建临时小画布（正方形，方便旋转）
        ch_img  = Image.new("RGBA", (char_w, _IMG_HEIGHT), (0, 0, 0, 0))
        ch_draw = ImageDraw.Draw(ch_img)
        color   = random.choice(_TEXT_COLORS)

        # 居中绘制字符
        try:
            bbox = ch_draw.textbbox((0, 0), ch, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError:
            tw, th = font.getsize(ch)
        cx = (char_w - tw) // 2
        cy = (_IMG_HEIGHT - th) // 2 - 2
        ch_draw.text((cx, cy), ch, font=font, fill=color + (255,))

        # 随机旋转 ±20°
        angle   = random.randint(-20, 20)
        ch_img  = ch_img.rotate(angle, resample=Image.BICUBIC, expand=False)

        # 粘贴到主画布（带轻微随机 Y 偏移）
        offset_x = i * char_w
        offset_y = random.randint(-4, 4)
        img.paste(ch_img, (offset_x, offset_y), ch_img)

    # Step 5：轻微模糊，增加识别难度
    img = img.filter(ImageFilter.SMOOTH_MORE)

    # Step 6：转为 Base64
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def generate_captcha() -> tuple[str, str]:
    """
    生成验证码并存入 Redis。

    流程：
      1. 随机生成 4 位字母数字字符串，统一转小写
      2. 绘制验证码图片，转 Base64
      3. 生成 UUID 作为 Redis Key（前缀 captcha:）
      4. 将小写文本以 TTL=300s 写入 Redis
      5. 返回 (uuid_str, base64_image)

    @return  (captcha_uuid: str, image_b64: str)
    """
    # Step 1：生成随机字符（统一小写，避免大小写混淆）
    text = "".join(random.choices(_CAPTCHA_CHARS, k=_CAPTCHA_LEN)).lower()

    # Step 2：绘制图片
    image_b64 = _draw_captcha_image(text)

    # Step 3 & 4：写入 Redis
    captcha_uuid = str(uuid.uuid4())
    redis_key    = f"{_REDIS_PREFIX}{captcha_uuid}"
    try:
        _get_redis().setex(redis_key, _CAPTCHA_TTL, text)
        logger.debug(f"[captcha] Generated uuid={captcha_uuid} text={text}")
    except Exception as e:
        logger.error(f"[captcha] Redis write failed: {e}")
        raise RuntimeError(f"Redis unavailable: {e}")

    return captcha_uuid, image_b64


def verify_captcha(captcha_uuid: str, user_input: str) -> bool:
    """
    校验验证码并在成功后立即销毁 Redis Key（防止重放攻击）。

    校验规则：
      - 忽略大小写（用户输入统一转小写后比对）
      - Key 不存在（过期或已使用）视为失败
      - 比对成功后立即 DELETE Key

    @param captcha_uuid  - 前端提交的 UUID
    @param user_input    - 用户输入的验证码字符串
    @return              - True=校验通过，False=失败
    """
    if not captcha_uuid or not user_input:
        return False

    redis_key = f"{_REDIS_PREFIX}{captcha_uuid}"
    try:
        stored = _get_redis().get(redis_key)
    except Exception as e:
        logger.error(f"[captcha] Redis read failed: {e}")
        return False

    if not stored:
        # Key 不存在：已过期或已被使用
        logger.warning(f"[captcha] Key not found or expired: {captcha_uuid}")
        return False

    ok = stored.lower() == user_input.strip().lower()

    if ok:
        # 验证通过后立即删除，防止同一验证码被多次提交（重放攻击）
        try:
            _get_redis().delete(redis_key)
            logger.debug(f"[captcha] Verified and deleted: {captcha_uuid}")
        except Exception as e:
            logger.warning(f"[captcha] Redis delete failed: {e}")
    else:
        logger.warning(f"[captcha] Mismatch uuid={captcha_uuid} input={user_input!r} stored={stored!r}")

    return ok
