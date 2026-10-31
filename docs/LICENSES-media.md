# Чужие медиа и библиотеки на сайте — источники и лицензии

| Файл | Что это | Автор / источник | Лицензия |
|---|---|---|---|
| `assets/brewing-coffee.2e74c5d9.json` | анимация «кофе наливается в чашку» в карточке «кофейная подписка» (блок «акция» на /, /kk/, /en/) | «Brewing coffee», автор **CAROLINA SALAZAR**, LottieFiles — https://lottiefiles.com/free-animation/brewing-coffee-0nUzAZmeIR | **Lottie Simple License** (бесплатно, коммерческое использование разрешено) |
| `assets/brewing-coffee-poster.f762aef7.webp` | статичный кадр той же анимации — без JS и при `prefers-reduced-motion` | то же | то же |
| `assets/lottie_light.23cd2c01.js` | плеер анимации: **lottie-web 5.12.2**, сборка light (`build/player/lottie_light.min.js`, только SVG, без expressions), байт в байт — sha256 `23cd2c01be3d4da8bb664645d03afaff40879c62dc5f8dfe075ab3aa35c108f3` (сверено: cdnjs и unpkg) | Airbnb — https://github.com/airbnb/lottie-web | **MIT** |
| значки «маршрут» и «позвонить» (SVG-спрайт в разметке /, /kk/, /en/, символы `i-pin`, `i-phone`) | кнопки карточек точек | **Lucide** 0.460.0, иконки `map-pin` и `phone` — https://lucide.dev (lucide-static) | **ISC** (часть исходников — Feather, MIT) |
| значок WhatsApp (символ `i-wa` того же спрайта) | кнопка WhatsApp в карточках точек | **Simple Icons** 13.21.0, иконка `whatsapp` — https://simpleicons.org | **CC0 1.0** (сам знак — товарный знак WhatsApp/Meta, используется для ссылки на чат) |

## Что изменено в анимации

Перекрашена под бренд скриптом `tools/lottie_brand.py` (исходник — `~/kofe-design-export/media/lottie/`, в репозиторий не кладём):
линии чашки (PNG внутри Lottie) — forest `#426349`, пар — forest 55 %, кофе — тёплый коричневый, как в оригинале (`#664430`).
Постер — тот же кадр, белый фон сделан прозрачным (видна светлая подложка карточки), обрезан как анимация в CSS. Движение не менялось.

## Значки

Пути взяты без изменений, цвет — `currentColor` (forest-кнопка — белый значок, остальные — цвет текста). Спрайт и кнопки собирает
`tools/seo_jsonld.py` (`ICONS`, `icon_link`). Эмодзи на кнопках не используются.

## Как подключено (анимация)

Карточку и загрузчик собирает `tools/seo_jsonld.py` (`sub_card`, `SUB_JS`, пути — `COFFEE_ANIM`). Плеер грузится лениво:
после `load` и только когда карточка видна (IntersectionObserver); вне экрана — пауза. Без JS, без IntersectionObserver и при
`prefers-reduced-motion: reduce` — постер. В preload и в PRECACHE `sw.js` плеера нет. Комментарий с автором и лицензиями —
рядом с карточкой в разметке страниц.
