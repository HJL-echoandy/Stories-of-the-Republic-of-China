#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《民国那些事儿》静态站点构建脚本（零依赖）。
读取 正文/ 下的 Markdown，生成 docs/ 静态站点：
  docs/index.html       总目录
  docs/style.css        样式
  docs/read/vXX_cYY.html  每章一页（含上一章/下一章导航）
  docs/.nojekyll        关闭 Jekyll 处理
运行：python tools/build_site.py
"""
import os
import re
import html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "正文")
OUT = os.path.join(ROOT, "docs")
READ = os.path.join(OUT, "read")

VOLUME_ORDER = [
    "第一卷_抽梯子",
    "第二卷_一地碎片",
    "第三卷_武人当国",
    "第四卷_南与北",
    "第五卷_十年",
    "第六卷_不死",
    "第七卷_大结局",
]

CN_NUM = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7,
          '八': 8, '九': 9, '十': 10}


def cn_to_int(s):
    return CN_NUM.get(s, 99)


def vol_index(vf):
    m = re.match(r'^第(.)卷', vf)
    return cn_to_int(m.group(1)) if m else 99


def cn_num_parse(s):
    """把中文数字（一~九、十、十一~十九）转成整数。"""
    if not s:
        return 999
    d = CN_NUM
    if '十' not in s:
        return d.get(s, 999)
    parts = s.split('十')
    left = parts[0]
    right = parts[1] if len(parts) > 1 else ''
    tens = 1 if left == '' else d.get(left, 0)
    ones = 0 if right == '' else d.get(right, 0)
    return tens * 10 + ones


def chap_num(fname):
    m = re.match(r'^第(.+?)章', fname)
    return cn_num_parse(m.group(1)) if m else 999


def inline(text):
    text = html.escape(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'【(.+?)】', r'<span class="marker">【\1】</span>', text)
    return text


def md_to_html(md):
    lines = md.split("\n")
    blocks = []
    cur = []
    for line in lines:
        if line.strip() == "":
            if cur:
                blocks.append(cur)
                cur = []
        else:
            cur.append(line)
    if cur:
        blocks.append(cur)

    out = []
    for block in blocks:
        first = block[0]
        if first.startswith("```"):
            inner = html.escape("\n".join(block[1:] if block[0].startswith("```") and len(block) > 1 else block))
            out.append("<pre><code>" + inner + "</code></pre>")
            continue
        if first.startswith("# "):
            out.append("<h1>" + inline(first[2:].strip()) + "</h1>")
        elif first.startswith("## "):
            out.append("<h2>" + inline(first[3:].strip()) + "</h2>")
        elif first.startswith("### "):
            out.append("<h3>" + inline(first[4:].strip()) + "</h3>")
        elif all(l.startswith(">") for l in block):
            inner = "<br>".join(inline(l.lstrip(">").strip()) for l in block)
            out.append("<blockquote>" + inner + "</blockquote>")
        elif first.strip() == "---":
            out.append("<hr>")
        elif re.match(r'^[-\*] ', first):
            items = []
            for l in block:
                m = re.match(r'^[-\*] (.*)', l)
                if m:
                    items.append("<li>" + inline(m.group(1)) + "</li>")
            out.append("<ul>" + "".join(items) + "</ul>")
        elif re.match(r'^\d+\. ', first):
            items = []
            for l in block:
                m = re.match(r'^\d+\. (.*)', l)
                if m:
                    items.append("<li>" + inline(m.group(1)) + "</li>")
            out.append("<ol>" + "".join(items) + "</ol>")
        else:
            para = "<br>".join(inline(l.strip()) for l in block)
            out.append("<p>" + para + "</p>")
    return "\n".join(out)


def read_title(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
    return os.path.basename(path)


def build():
    os.makedirs(READ, exist_ok=True)

    volumes = []
    all_chapters = []  # 全局顺序，用于上一章/下一章

    for vi, vf in enumerate(sorted(VOLUME_ORDER, key=vol_index), start=1):
        vpath = os.path.join(SRC, vf)
        if not os.path.isdir(vpath):
            continue
        parts = vf.split("_", 1)
        label = parts[0]
        sub = parts[1] if len(parts) > 1 else ""
        files = [f for f in os.listdir(vpath) if f.endswith(".md")]
        chapters = []
        for ci, fname in enumerate(sorted(files, key=chap_num), start=1):
            fpath = os.path.join(vpath, fname)
            title = read_title(fpath)
            slug = "v%02d_c%02d.html" % (vi, ci)
            rec = {"title": title, "slug": slug, "vol_label": label,
                   "vol_sub": sub, "file": fname}
            chapters.append(rec)
            all_chapters.append(rec)
        volumes.append({"label": label, "sub": sub, "chapters": chapters})

    # 总目录
    toc_items = []
    for v in volumes:
        name = v["label"] + ((" · " + v["sub"]) if v["sub"] else "")
        lis = "".join(
            '<li><a href="read/%s">%s</a></li>' % (c["slug"], html.escape(c["title"]))
            for c in v["chapters"]
        )
        toc_items.append(
            '<section class="vol">\n<h2>%s</h2>\n<ul class="chlist">%s</ul>\n</section>'
            % (html.escape(name), lis)
        )
    toc_html = "\n".join(toc_items)

    index_html = INDEX_TEMPLATE % {
        "toc": toc_html,
        "total": len(all_chapters),
    }
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    # 各章页面
    for idx, ch in enumerate(all_chapters):
        prev_link = ""
        next_link = ""
        if idx > 0:
            p = all_chapters[idx - 1]
            prev_link = '<a class="navbtn" href="%s">&larr; 上一章：%s</a>' % (
                p["slug"], html.escape(p["title"]))
        if idx < len(all_chapters) - 1:
            n = all_chapters[idx + 1]
            next_link = '<a class="navbtn" href="%s">下一章：%s &rarr;</a>' % (
                n["slug"], html.escape(n["title"]))
        # 读取并转换正文
        fpath = None
        for v in volumes:
            if v["label"] == ch["vol_label"]:
                for fname in os.listdir(os.path.join(SRC, v["label"] + ("_" + v["sub"] if v["sub"] else ""))):
                    if fname == ch["file"]:
                        fpath = os.path.join(SRC, v["label"] + ("_" + v["sub"] if v["sub"] else ""), fname)
                break
        with open(fpath, encoding="utf-8") as f:
            raw = f.read()
        content = md_to_html(raw)
        vol_name = ch["vol_label"] + ((" · " + ch["vol_sub"]) if ch["vol_sub"] else "")
        page = CHAPTER_TEMPLATE % {
            "title": html.escape(ch["title"]),
            "vol_name": html.escape(vol_name),
            "content": content,
            "prev": prev_link,
            "next": next_link,
        }
        with open(os.path.join(READ, ch["slug"]), "w", encoding="utf-8") as f:
            f.write(page)

    # 样式
    with open(os.path.join(OUT, "style.css"), "w", encoding="utf-8") as f:
        f.write(STYLE_CSS)

    # 关闭 Jekyll
    with open(os.path.join(OUT, ".nojekyll"), "w", encoding="utf-8") as f:
        f.write("")

    print("生成完成：%d 章，%d 卷" % (len(all_chapters), len(volumes)))


INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>民国那些事儿</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="site-head">
  <h1>民国那些事儿</h1>
  <p class="sub">1905 — 1949，用《明朝那些事儿》的笔法，写一部通俗民国史话</p>
</header>
<main class="wrap">
  <p class="intro">从 1905 年那道被抽走的科举梯子，到 1949 年天安门上的宣告。七卷，%(total)d 章，把那些被赶出门的年轻人、握枪的人、拿笔的人，一个一个讲给你听。</p>
  %(toc)s
</main>
<footer class="site-foot">
  <p>本作品采用 <a href="LICENSE">知识共享署名-非商业性使用-禁止演绎 4.0 国际许可协议 (CC BY-NC-ND 4.0)</a> 进行许可。</p>
</footer>
</body>
</html>
"""

CHAPTER_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s · 民国那些事儿</title>
<link rel="stylesheet" href="../style.css">
</head>
<body>
<header class="site-head">
  <h1><a href="../index.html">民国那些事儿</a></h1>
  <p class="sub">%(vol_name)s</p>
</header>
<main class="wrap">
  <article class="chapter">
%(content)s
  </article>
  <nav class="pager">
    %(prev)s
    %(next)s
  </nav>
</main>
<footer class="site-foot">
  <p><a href="../index.html">← 返回总目录</a></p>
  <p>本作品采用 <a href="../LICENSE">知识共享署名-非商业性使用-禁止演绎 4.0 国际许可协议 (CC BY-NC-ND 4.0)</a> 进行许可。</p>
</footer>
</body>
</html>
"""

STYLE_CSS = """* { box-sizing: border-box; }
body {
  margin: 0;
  background: #faf7f0;
  color: #2b2620;
  font-family: "Noto Serif SC", "Songti SC", "SimSun", Georgia, serif;
  line-height: 1.95;
  font-size: 18px;
}
.site-head {
  text-align: center;
  padding: 40px 20px 24px;
  border-bottom: 1px solid #e4dccb;
  background: #fffdf8;
}
.site-head h1 {
  margin: 0;
  font-size: 30px;
  letter-spacing: 4px;
}
.site-head h1 a { color: inherit; text-decoration: none; }
.site-head .sub { margin: 8px 0 0; color: #8a7d66; font-size: 15px; letter-spacing: 1px; }
.wrap { max-width: 760px; margin: 0 auto; padding: 32px 22px 60px; }
.intro {
  background: #fffdf8; border: 1px solid #ece3d2; border-radius: 8px;
  padding: 18px 22px; color: #5a5040; font-size: 16px; margin-bottom: 34px;
}
.vol { margin-bottom: 30px; }
.vol h2 {
  font-size: 21px; border-left: 4px solid #b5462f; padding-left: 12px;
  margin: 0 0 12px; color: #3a3128;
}
.chlist { list-style: none; padding: 0; margin: 0; columns: 2; column-gap: 28px; }
.chlist li { break-inside: avoid; margin: 0 0 8px; }
.chlist a { color: #2f6f8f; text-decoration: none; }
.chlist a:hover { text-decoration: underline; }
.chapter h1 { font-size: 26px; text-align: center; margin: 6px 0 28px; letter-spacing: 2px; }
.chapter h2 { font-size: 21px; margin: 34px 0 12px; color: #3a3128; border-bottom: 1px dashed #ddd2bd; padding-bottom: 6px; }
.chapter h3 { font-size: 18px; margin: 26px 0 10px; color: #4a4036; }
.chapter p { margin: 0 0 16px; text-indent: 2em; }
.chapter blockquote {
  margin: 18px 0; padding: 12px 20px; background: #f3ede0;
  border-left: 4px solid #c9a96a; color: #5a5040; border-radius: 0 6px 6px 0;
}
.chapter blockquote p { text-indent: 0; margin: 0; }
.chapter hr { border: none; border-top: 1px solid #e0d6c2; margin: 30px 0; }
.chapter ul, .chapter ol { margin: 0 0 16px; padding-left: 2.2em; }
.chapter li { margin: 0 0 6px; }
.marker { color: #b5462f; font-weight: 600; }
.pager { display: flex; justify-content: space-between; gap: 12px; margin-top: 44px; border-top: 1px solid #e4dccb; padding-top: 22px; flex-wrap: wrap; }
.navbtn { color: #2f6f8f; text-decoration: none; font-size: 15px; }
.navbtn:hover { text-decoration: underline; }
.site-foot { text-align: center; padding: 26px 20px 40px; color: #8a7d66; font-size: 14px; }
.site-foot a { color: #2f6f8f; }
@media (max-width: 600px) { .chlist { columns: 1; } body { font-size: 17px; } }
"""


if __name__ == "__main__":
    build()
