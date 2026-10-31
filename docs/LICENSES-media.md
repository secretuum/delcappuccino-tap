# Чужие медиа и библиотеки на сайте — источники и лицензии

| Файл | Что это | Автор / источник | Лицензия |
|---|---|---|---|
| `assets/latte-pour.0aa34e2d.webm`, `assets/latte-pour.eaff9eed.mp4` | видео «наливают кофе» в плитке «кофейная подписка» (блок «акции» на /, /kk/, /en/): латте-арт, рисуется сердце | Mixkit, «Latte art» — https://mixkit.co/free-stock-video/latte-art-810/ (исходник `mixkit-810-latte-art-pour-720.mp4`, 1280×720, 34 с) | **Mixkit Stock Video Free License** — бесплатно, коммерческое использование разрешено, атрибуция не нужна; исходник нельзя раздавать как сток (в репозиторий не кладём) |
| `assets/latte-pour-poster.eace987c.webp` | постер того же видео — без JS и при `prefers-reduced-motion` | то же, кадр 33 с | то же |
| значки «маршрут» и «позвонить» (SVG-спрайт в разметке /, /kk/, /en/, символы `i-pin`, `i-phone`) | кнопки карточек точек | **Lucide** 0.460.0, иконки `map-pin` и `phone` — https://lucide.dev (lucide-static) | **ISC** (часть исходников — Feather, MIT) |
| значок WhatsApp (символ `i-wa` того же спрайта) | кнопка WhatsApp в карточках точек и в окне выбора филиала (заливка #25D366) | **Simple Icons** 13.21.0, иконка `whatsapp` — https://simpleicons.org | **CC0 1.0** (сам знак — товарный знак WhatsApp/Meta, используется для ссылки на чат) |
| значки Instagram, YouTube, Threads (символы `i-ig`, `i-yt`, `i-th`) | ряд соцсетей в блоке «загляните на кофе» | **Simple Icons** 13.21.0, иконки `instagram`, `youtube`, `threads` — https://simpleicons.org | **CC0 1.0** (сами знаки — товарные знаки Meta и Google, используются для ссылок на страницы сети) |

## Что вырезано из видео и как

Клип собирает `tools/build_sub_video.py` (ffmpeg) из исходника вне репозитория — пересборка воспроизводима:
весь налив 0–31 с (эспрессо → молоко → сердце) ускорен в 2 раза; петля без рывка — последние 0,5 с плавно перетекают в
начало (xfade), клип начинается с 0,5 с — длина 15 с; кадр 1057×720 справа под пропорцию плитки 910:620 (в начале чашка
справа, в конце — в центре), 960×654, 24 к/с, без звука. WebM VP9 (CRF 38) — первым `<source>`, MP4 H.264 (CRF 27, yuv420p,
faststart) — вторым. Постер — webp кадра 33 с (сердце готово, питчер убран), 640×436.

До 1.11 в плитке была Lottie-анимация «Brewing coffee» (CAROLINA SALAZAR, Lottie Simple License) с плеером lottie-web light
(MIT); по решению владельца её заменило видео, файлы анимации, плеер и `tools/lottie_brand.py` удалены.

## Значки

Пути взяты без изменений, цвет — `currentColor` (forest-кнопка — белый значок, остальные — цвет текста). Спрайт и кнопки собирает
`tools/seo_jsonld.py` (`ICONS`, `icon_link`). Эмодзи на кнопках не используются.

## Как подключено (видео)

Плитку и загрузчик собирает `tools/seo_jsonld.py` (`sub_card`, `SUB_JS`, пути — `SUB_VIDEO`): `<video muted loop playsinline
preload="none" poster>` во всю плитку, `object-fit:cover`. Видео грузится и играет только когда плитка на экране
(IntersectionObserver, после `load`), вне экрана — пауза. Без JS, без IntersectionObserver и при `prefers-reduced-motion: reduce`
— постер. В preload и в PRECACHE `sw.js` видео нет (sw.js пропускает mp4/webm мимо кэша). Комментарий с источником и лицензией —
рядом с плиткой в разметке страниц.
