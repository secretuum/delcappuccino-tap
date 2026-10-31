# Чужие медиа и библиотеки на сайте — источники и лицензии

| Файл | Что это | Автор / источник | Лицензия |
|---|---|---|---|
| `assets/brewing-coffee.df6fc172.json` | анимация «кофе наливается в чашку» в плитке «кофейная подписка» (блок «акции» на /, /kk/, /en/); линии кремовые на зелёной плитке | «Brewing coffee», автор **CAROLINA SALAZAR**, LottieFiles — https://lottiefiles.com/free-animation/brewing-coffee-0nUzAZmeIR | **Lottie Simple License** (бесплатно, коммерческое использование разрешено) |
| `assets/brewing-coffee-poster.b7411dfe.webp` | статичный кадр той же анимации — без JS и при `prefers-reduced-motion` | то же | то же |
| `assets/lottie_light.23cd2c01.js` | плеер анимации: **lottie-web 5.12.2**, сборка light (`build/player/lottie_light.min.js`, только SVG, без expressions), байт в байт — sha256 `23cd2c01be3d4da8bb664645d03afaff40879c62dc5f8dfe075ab3aa35c108f3` (сверено: cdnjs и unpkg) | Airbnb — https://github.com/airbnb/lottie-web | **MIT** |
| значки «маршрут» и «позвонить» (SVG-спрайт в разметке /, /kk/, /en/, символы `i-pin`, `i-phone`) | кнопки карточек точек | **Lucide** 0.460.0, иконки `map-pin` и `phone` — https://lucide.dev (lucide-static) | **ISC** (часть исходников — Feather, MIT) |
| значок WhatsApp (символ `i-wa` того же спрайта) | кнопка WhatsApp в карточках точек и в окне выбора филиала (заливка #25D366) | **Simple Icons** 13.21.0, иконка `whatsapp` — https://simpleicons.org | **CC0 1.0** (сам знак — товарный знак WhatsApp/Meta, используется для ссылки на чат) |
| значки Instagram, YouTube, Threads (символы `i-ig`, `i-yt`, `i-th`) | ряд соцсетей в блоке «загляните на кофе» | **Simple Icons** 13.21.0, иконки `instagram`, `youtube`, `threads` — https://simpleicons.org | **CC0 1.0** (сами знаки — товарные знаки Meta и Google, используются для ссылок на страницы сети) |

## Что изменено в анимации

Перекрашена под бренд скриптом `tools/lottie_brand.py` (исходник — `~/kofe-design-export/media/lottie/`, в репозиторий не кладём):
линии чашки (PNG внутри Lottie) — кремовый бренда `#FEF1E7`, пар — он же 55 %, кофе — тёплый коричневый, как в оригинале
(`#664430`); плитка — фирменный зелёный. Первая версия (линии forest на светлой карточке) удалена 1.11 — страницы на неё
не ссылались.
Постер — тот же кадр, белый фон сделан прозрачным (видна зелёная плитка), обрезан как анимация в CSS. Движение не менялось.

## Значки

Пути взяты без изменений, цвет — `currentColor` (forest-кнопка — белый значок, остальные — цвет текста). Спрайт и кнопки собирает
`tools/seo_jsonld.py` (`ICONS`, `icon_link`). Эмодзи на кнопках не используются.

## Как подключено (анимация)

Карточку и загрузчик собирает `tools/seo_jsonld.py` (`sub_card`, `SUB_JS`, пути — `COFFEE_ANIM`). Плеер грузится лениво:
после `load` и только когда карточка видна (IntersectionObserver); вне экрана — пауза. Без JS, без IntersectionObserver и при
`prefers-reduced-motion: reduce` — постер. Проигрывается отрезок кадров 10–175 (на кадрах 0–9 чашка вырастает из
точки — их не показываем), до запуска и на паузе стоит кадр 150 с полной чашкой; постер прячется по `DOMLoaded`. В preload и в PRECACHE `sw.js` плеера нет. Комментарий с автором и лицензиями —
рядом с карточкой в разметке страниц.
