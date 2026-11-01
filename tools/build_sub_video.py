#!/usr/bin/env python3
"""Видео для плитки «кофейная подписка» в блоке «акции» на /, /kk/, /en/ (решение владельца 1.11.2026: вместо Lottie-чашки —
реальное видео, где наливают кофе).

Исходник: Mixkit «Latte art» (https://mixkit.co/free-stock-video/latte-art-810/), файл mixkit-810-latte-art-pour-720.mp4
(1280×720, 24 к/с, 34 с), Mixkit Stock Video Free License — бесплатно, коммерция разрешена, атрибуция не нужна, исходник нельзя
раздавать как сток. Поэтому сам исходник в репозиторий не кладём: путь — аргументом.

Что делаем: весь налив 0–31 с (эспрессо → молоко → сердце) ускорен в 2 раза — 15,5 с; петля без рывка: последние 0,5 с
плавно перетекают в начало (xfade), клип начинается с 0,5 с исходника — длина 15 с. Кадр — под пропорцию плитки 910:620
(1057×720 справа: в начале чашка справа, в конце — в центре, вся в кадре), 960×654, без звука. H.264 (yuv420p, faststart)
и VP9 webm (первым <source>); постер — webp кадра 33 с (сердце готово, питчер убран).

Запуск из корня репозитория:
    python3 tools/build_sub_video.py ~/kofe-design-export/media/video/mixkit-810-latte-art-pour-720.mp4 [папка, по умолчанию assets]
Печатает имена файлов с хэшем — вписать в SUB_VIDEO (tools/seo_jsonld.py), пересобрать (seo_jsonld.py, sw_version.py).
Нужен ffmpeg (libx264, libvpx-vp9, libwebp). Лицензии — docs/LICENSES-media.md.
"""
import hashlib, os, shutil, subprocess, sys, tempfile

START, END, SPEED, XFADE = 0.0, 31.0, 2.0, 0.5         # кусок исходника, ускорение, перетекание конца в начало (с, после ускорения)
CROP = 'crop=1057:720:223:0'                            # 910:620 ≈ 1,468 по высоте 720, прижато вправо
W, H = 960, 654
POSTER_T = 33.0                                         # кадр постера в исходнике
X264 = ['-c:v', 'libx264', '-preset', 'veryslow', '-crf', '27', '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-movflags', '+faststart']
VP9 = ['-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', '38', '-row-mt', '1', '-deadline', 'good', '-cpu-used', '1', '-pix_fmt', 'yuv420p', '-fflags', '+bitexact']   # bitexact: webm без случайных UID — одинаковый хэш при пересборке


def run(args):
    subprocess.run(['ffmpeg', '-v', 'error', '-y'] + args, check=True)


def hashed(path, name, ext, out):
    with open(path, 'rb') as f:
        h = hashlib.sha256(f.read()).hexdigest()[:8]
    dst = os.path.join(out, '%s.%s.%s' % (name, h, ext))
    shutil.copyfile(path, dst)
    print('%-44s %7.0f КБ' % (os.path.relpath(dst), os.path.getsize(dst) / 1024))
    return dst


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = os.path.expanduser(sys.argv[1])
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets')
    length = (END - START) / SPEED
    base = ('[0:v]trim=%s:%s,setpts=(PTS-STARTPTS)/%s,fps=24,%s,scale=%d:%d:flags=lanczos,setsar=1,split[a][b];'
            % (START, END, SPEED, CROP, W, H))
    # [a] — с XFADE до конца, [b] — первые XFADE: конец [a] перетекает в начало [b] → петля замыкается на кадре XFADE
    graph = (base + '[a]trim=%s,setpts=PTS-STARTPTS[body];[b]trim=0:%s,setpts=PTS-STARTPTS[head];'
             '[body][head]xfade=transition=fade:duration=%s:offset=%s,format=yuv420p[v]'
             % (XFADE, XFADE, XFADE, length - 2 * XFADE))
    with tempfile.TemporaryDirectory() as d:
        mp4, webm, webp = os.path.join(d, 'v.mp4'), os.path.join(d, 'v.webm'), os.path.join(d, 'p.webp')
        run(['-i', src, '-filter_complex', graph, '-map', '[v]', '-an'] + X264 + [mp4])
        run(['-i', src, '-filter_complex', graph, '-map', '[v]', '-an'] + VP9 + [webm])
        run(['-ss', str(POSTER_T), '-i', src, '-frames:v', '1', '-vf', '%s,scale=%d:%d:flags=lanczos' % (CROP, 640, 436),
             '-c:v', 'libwebp', '-quality', '62', webp])
        for path, name, ext in ((mp4, 'latte-pour', 'mp4'), (webm, 'latte-pour', 'webm'), (webp, 'latte-pour-poster', 'webp')):
            hashed(path, name, ext, out)


if __name__ == '__main__':
    main()
