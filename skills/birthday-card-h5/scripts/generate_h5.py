#!/usr/bin/env python3
"""
生日祝福H5生成脚本 - 生成完全离线、嵌入所有资源的单HTML文件

输入：6张水彩插图 + 1首BGM音频
输出：单HTML文件，打开后有首页"开始"按钮，点击后播放音乐+自动翻页

使用方法：
  python3 generate_h5.py --images /path/to/page1.jpg /path/to/page2.jpg ... --bgm /path/to/bgm.mp3 --output /path/to/output.html
  
参数：
  --images  6张水彩插图路径（顺序对应6页）
  --bgm     BGM音频文件路径（mp3格式）
  --output  输出HTML文件路径（默认 /tmp/birthday_card/index.html）
  --name    祝福对象姓名（默认"小明"）
  --max-img-size  图片最大宽度像素（默认800，越大越清晰）
  --quality  图片JPEG质量（1-100，默认95）
  --bgm-start-sec BGM截取起始秒数（默认0，从头开始）
  --bgm-duration-sec BGM截取时长秒数（默认0=完整嵌入）
"""

import argparse, base64, os, sys
from PIL import Image
from io import BytesIO
import re

PAGE_COPIES = [
    ("嘿{name}，又到你的生日了。认识你这些年，最庆幸的就是身边一直有你在。🎂",
     "新的一岁不求别的，只愿你做自己、爱自己，好事自然会来找你。"),
    ("一起熬过的夜、聊过的天、走过的路，都是我一直放在心里的感动。☕",
     "有些朋友不需要天天联系，但一见面就知道——没变，真好。"),
    ("知道你这个人好强，什么事都自己扛。但在我这，你可以不用逞强。🌙",
     "偶尔脆弱一下，天不会塌下来，我也不会笑话你。"),
    ("其实你比你以为的要优秀得多。只是你总爱跟自己较劲，忘了停下来夸夸自己。✨",
     '新的一岁，少点自我怀疑，多点"我行"。你真的可以。'),
    ("生活不用每天都精彩，平平安安就很好。能一起散散步聊聊近况，就是最好的日子。🍃",
     "不管几岁，在朋友眼里你永远是那个笑起来很温暖的样子。"),
    ("最后一句真心话——有你这个朋友，是我的运气。🍻",
     "生日快乐，{name}。年年有今日，年年有我在。"),
]

GRADIENTS = [
    "linear-gradient(135deg,#fef6fb,#f0f4ff,#e8f5e9)",
    "linear-gradient(135deg,#fff8f0,#f3eefc,#e0f2fe)",
    "linear-gradient(135deg,#f0fdf4,#fff7ed,#fef2f2)",
    "linear-gradient(135deg,#f5f3ff,#fce7f3,#ecfdf5)",
    "linear-gradient(135deg,#fff1f2,#f0f9ff,#f5f5f4)",
    "linear-gradient(135deg,#fdf4ff,#fef9c3,#dbeafe)",
]

ANIM_CLASSES = ["f1","f2","f3","f4","f5","f6"]
ANIM_KEYFRAMES = """
@keyframes a1{0%,100%{transform:translateY(0) scale(1)}50%{transform:translateY(-10px) scale(1.02)}}
@keyframes a2{0%,100%{transform:translateX(0)}50%{transform:translateX(8px)}}
@keyframes a3{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(.97);opacity:.9}}
@keyframes a4{0%,100%{transform:scale(1) rotate(0)}50%{transform:scale(1.03) rotate(1deg)}}
@keyframes a5{0%,100%{transform:translateY(0) rotate(0)}50%{transform:translateY(-6px) rotate(1.2deg)}}
@keyframes a6{0%,100%{transform:rotate(-2deg)}50%{transform:rotate(2deg)}}
"""

def encode_image(path, max_size=800, quality=95, no_resize=False):
    """编码图片为base64 data URI。no_resize=True 时保留原图完整尺寸"""
    if no_resize:
        # 用户原始照片：不缩放、不裁切，保持原图完整尺寸
        with open(path, "rb") as f:
            data = f.read()
        ext = os.path.splitext(path)[1].lower()
        mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"
    img = Image.open(path)
    w, h = img.size
    if w > max_size:
        r = max_size / w
        img = img.resize((max_size, int(h * r)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, "JPEG", quality=quality)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"

def encode_audio(path, start_sec=0, duration_sec=0):
    """编码音频为base64 data URI。默认不截取=完整嵌入"""
    with open(path, "rb") as f:
        data = f.read()
    if duration_sec > 0:
        # 粗略截取：按起始位置+时长取原始字节
        # 注意：mp3只能近似截取，不保证帧边界对齐
        total_duration = None
        try:
            import subprocess
            r = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "csv=p=0", path],
                capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0:
                total_duration = float(r.stdout.strip())
        except: pass

        if total_duration and total_duration > 0:
            bytes_per_sec = len(data) / total_duration
            start_byte = max(0, int(start_sec * bytes_per_sec))
            end_byte = min(len(data), int((start_sec + duration_sec) * bytes_per_sec))
            data = data[start_byte:end_byte]

    return f"data:audio/mpeg;base64,{base64.b64encode(data).decode()}"

def build_html(name, img_b64s, audio_b64, img_paths, auto_slide_sec=5, custom_texts=None):
    """构建完整HTML"""
    # 检测每张图片方向：竖图用contain保证完整显示，横图用cover+16:9
    from PIL import Image
    img_styles = []
    for path in img_paths:
        try:
            im = Image.open(path)
            w, h = im.size
            is_portrait = h > w * 1.05  # 高>宽1.05倍视为竖图
            im.close()
        except:
            is_portrait = False
        if is_portrait:
            # 竖图：contain模式，自动高度，完整显示人头
            img_styles.append('pic-portrait')
        else:
            # 横图/方图：保持原有16:9 cover
            img_styles.append('pic')

    pages_html = ""
    for i in range(6):
        if custom_texts and i < len(custom_texts):
            t1, t2 = custom_texts[i]
        else:
            t1, t2 = PAGE_COPIES[i]
        g = GRADIENTS[i]
        ac = ANIM_CLASSES[i]
        pic_cls = img_styles[i] + " " + ac
        n = i + 1
        hint = "向上滑动" if i < 5 else "🎉"
        bg_style = f"background:{g};position:relative"
        bg_img = f'''<div class="bg-illus" style="background-image:url('{img_b64s[i]}')"></div>'''
        pages_html += f'''<div class="p" style="{bg_style}">{bg_img}<div class="num">{n}/6</div><div class="{pic_cls}"><img src="{img_b64s[i]}"></div><div class="txt"><p class="l1">{t1}</p><p class="l2">{t2}</p></div><div class="hint">{hint}</div></div>\n'''

    # 将用户名字替换进文案
    pages_html = pages_html.replace("{name}", name)

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
<title>生日快乐 · {name}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:100%;height:100%;overflow:hidden;font-family:'PingFang SC','Microsoft YaHei',sans-serif;background:#fce4ec}}
#splash{{position:fixed;inset:0;z-index:9999;background:linear-gradient(135deg,#fce4ec 0%,#e8eaf6 50%,#e3f2fd 100%);display:flex;flex-direction:column;align-items:center;justify-content:center;transition:opacity 1s,visibility 1s}}
#splash.hide{{opacity:0;visibility:hidden;pointer-events:none}}
#splash .emoji{{font-size:64px;margin-bottom:16px;animation:s1 3s ease-in-out infinite}}
@keyframes s1{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-12px)}}}}
#splash h1{{font-size:28px;color:#5a4a4a;margin-bottom:8px;font-weight:700}}@media (min-width:1024px){{#splash h1{{font-size:36px}}#splash .emoji{{font-size:80px}}#splash p{{font-size:18px}}#splash .btn{{font-size:22px;padding:16px 64px}}}}@media (min-width:1440px){{#splash h1{{font-size:42px}}#splash .emoji{{font-size:96px}}}}
#splash p{{font-size:15px;color:#7a6a6a;margin-bottom:32px;opacity:0.8}}
#splash .btn{{background:rgba(255,255,255,0.7);backdrop-filter:blur(12px);padding:14px 56px;border-radius:28px;border:none;font-size:19px;color:#5a4a4a;font-weight:600;cursor:pointer;box-shadow:0 4px 20px rgba(0,0,0,0.08);transition:transform 0.2s;-webkit-tap-highlight-color:transparent}}
#splash .btn:active{{transform:scale(0.92)}}
#wrap{{width:100%;height:100%;overflow-y:scroll;overflow-x:hidden;scroll-snap-type:y mandatory;-webkit-overflow-scrolling:touch}}
.p{{width:100%;height:100vh;height:100dvh;scroll-snap-align:start;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:30px 20px;position:relative}}
.pic,.pic-portrait{{border-radius:16px;overflow:hidden;box-shadow:0 8px 28px rgba(0,0,0,.07);margin-bottom:20px;flex-shrink:0;transition:transform .4s}}
.pic{{width:min(90vw,420px);aspect-ratio:16/9}}
.pic-portrait{{width:min(65vw,350px);max-height:min(70vh,550px);display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.03)}}
@media (min-width:768px){{.pic{{width:70vw;max-width:580px}}.pic-portrait{{width:min(55vw,400px);max-height:min(65vh,600px)}}}}@media (min-width:1024px){{.pic{{width:65vw;max-width:680px}}.pic-portrait{{width:min(50vw,450px);max-height:min(60vh,650px)}}.txt .l1,.txt .l2{{font-size:22px;line-height:1.8}}}}@media (min-width:1440px){{.pic{{width:50vw;max-width:780px}}.pic-portrait{{width:min(40vw,500px);max-height:min(55vh,700px)}}.txt .l1,.txt .l2{{font-size:24px;line-height:1.9}}.txt{{max-width:700px}}}}
.pic:hover,.pic-portrait:hover{{transform:scale(1.02)}}
.pic img{{width:100%;height:100%;object-fit:cover;display:block}}
.pic-portrait img{{width:100%;height:100%;object-fit:contain;display:block}}
.f1{{animation:a1 4s ease-in-out infinite}}.f2{{animation:a2 5s ease-in-out infinite}}.f3{{animation:a3 3.5s ease-in-out infinite}}
.f4{{animation:a4 3s ease-in-out infinite}}.f5{{animation:a5 4s ease-in-out infinite}}.f6{{animation:a6 6s ease-in-out infinite}}
{ANIM_KEYFRAMES}
.txt{{text-align:center;width:100%;max-width:480px}}
.txt .l1,.txt .l2{{opacity:0;transition:opacity .8s,transform .8s;transform:translateY(20px)}}
.txt .l1{{transition-delay:.3s}}.txt .l2{{transition-delay:1.2s}}
.p.active .txt .l1,.p.active .txt .l2{{opacity:1;transform:translateY(0)}}
.txt p{{font-size:17px;line-height:1.7;color:#4a3f3f;font-weight:500;letter-spacing:.5px}}
.txt p:first-child{{margin-bottom:8px}}
#btn{{position:fixed;top:12px;right:12px;z-index:888;width:38px;height:38px;border-radius:50%;background:rgba(255,255,255,.7);backdrop-filter:blur(8px);border:none;font-size:18px;cursor:pointer;box-shadow:0 2px 10px rgba(0,0,0,.08);display:none;align-items:center;justify-content:center}}
.hint{{position:absolute;bottom:18px;left:50%;transform:translateX(-50%);color:rgba(90,74,74,.35);font-size:13px;animation:bn 2s infinite}}
@keyframes bn{{0%,100%{{transform:translateX(-50%) translateY(0)}}50%{{transform:translateX(-50%) translateY(-6px)}}}}
.num{{position:absolute;top:16px;left:16px;color:rgba(90,74,74,.25);font-size:12px;font-weight:400}}
.bg-illus{{position:absolute;inset:0;background-size:cover;background-position:center;opacity:.2;pointer-events:none;animation:bgBreathe 10s ease-in-out infinite;filter:saturate(0.7) blur(1px)}}
@keyframes bgBreathe{{0%,100%{{opacity:.18;transform:scale(1)}}50%{{opacity:.25;transform:scale(1.03)}}}}
#wrap::-webkit-scrollbar{{display:none}}#wrap{{-ms-overflow-style:none;scrollbar-width:none}}
</style>
</head>
<body>
<div id="splash">
  <div class="emoji">🎂</div>
  <h1>✨ {name}，生日快乐 ✨</h1>
  <p>有一份温暖的祝福，正在等你开启</p>
  <button class="btn" id="startBtn">🎉 开始</button>
</div>
<button id="btn" onclick="tm()">🔊</button>
<audio id="a" loop></audio>
<div id="wrap"></div>
<script>
(function(){{
var a=document.getElementById('a');
a.src='{audio_b64}';
a.volume=0.3;var m=false,autoTimer=null;
document.getElementById('wrap').innerHTML=`{pages_html}`;
var o=new IntersectionObserver(function(e){{e.forEach(function(x){{x.target.classList.toggle('active',x.isIntersecting)}})}},{{threshold:0.5}});
document.querySelectorAll('.p').forEach(function(p){{o.observe(p)}});
document.getElementById('startBtn').addEventListener('click',function(){{
  a.play().then(function(){{
    document.getElementById('splash').classList.add('hide');
    document.getElementById('btn').style.display='flex';
    var ps=document.querySelectorAll('.p');var idx=0;
    autoTimer=setInterval(function(){{idx++;if(idx>=ps.length)idx=0;ps[idx].scrollIntoView({{behavior:'smooth'}})}},{auto_slide_sec*1000});
  }}).catch(function(e){{console.log(e)}});
}});
function tm(){{m=!m;a.muted=m;document.getElementById('btn').textContent=m?'🔇':'🔊'}}
document.getElementById('wrap').addEventListener('touchstart',function(){{if(autoTimer){{clearInterval(autoTimer);autoTimer=null}}}});
document.getElementById('wrap').addEventListener('scroll',function(){{if(autoTimer){{clearInterval(autoTimer);autoTimer=null}}}});
}})();
</script>
</body>
</html>'''

def main():
    parser = argparse.ArgumentParser(description="生成生日祝福H5单HTML文件")
    parser.add_argument("--images", nargs=6, required=True,
                        help="6张图片路径（顺序对应6页）")
    parser.add_argument("--bgm", required=True, help="BGM音频文件路径（mp3格式）")
    parser.add_argument("--output", default="/tmp/birthday_card/index.html",
                        help="输出HTML文件路径")
    parser.add_argument("--name", default="小明", help="祝福对象姓名")
    parser.add_argument("--max-img-size", type=int, default=800,
                        help="图片最大宽度像素（默认800，AI生图时使用）")
    parser.add_argument("--quality", type=int, default=95,
                        help="图片JPEG质量（1-100，默认95，确保清晰）")
    parser.add_argument("--bgm-duration-sec", type=int, default=0,
                        help="BGM截取时长秒数（0=完整嵌入）")
    parser.add_argument("--texts", nargs=12, default=None,
                        help="12条文案（每页2条，共6页顺序排列）")
    parser.add_argument("--no-resize", action="store_true",
                        help="不缩放图片，保留用户原始照片完整尺寸和原图质量")
    args = parser.parse_args()

    print(f"编码图片...")
    img_b64s = []
    for i, p in enumerate(args.images):
        if args.no_resize:
            print(f"  [{i+1}/6] 使用原图完整尺寸（不缩放）: {p}")
            img_b64s.append(encode_image(p, 0, 0, no_resize=True))
        else:
            img_b64s.append(encode_image(p, args.max_img_size, args.quality))

    # 解析自定义文案
    custom_texts = None
    if args.texts:
        custom_texts = [(args.texts[i*2], args.texts[i*2+1]) for i in range(6)]
        print(f"使用自定义文案（共6页）")

    print(f"编码音频...")
    audio_b64 = encode_audio(args.bgm, duration_sec=args.bgm_duration_sec)

    print(f"构建HTML（祝福对象：{args.name}）...")
    html = build_html(args.name, img_b64s, audio_b64, args.images, auto_slide_sec=5, custom_texts=custom_texts)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    size = os.path.getsize(args.output)
    print(f"\n✅ 生成成功: {args.output}")
    print(f"  文件大小: {size/1024:.1f}KB ({size/1024/1024:.2f}MB)")
    print(f"  使用方法：在手机浏览器中打开该HTML文件")
    print(f"           → 点击「🎉 开始」按钮播放音乐+自动翻页")

if __name__ == "__main__":
    main()
