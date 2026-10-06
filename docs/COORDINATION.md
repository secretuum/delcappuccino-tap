# Координация — Taplink del Cappuccino

Журнал главного терминала части (`taplink-del-cappuccino-master`).
Главная ветка — `master`. Задачи живут в копиях `.claude/worktrees/<задача>` на ветках `worktree-<задача>`.
Сливает пул-реквесты, пушит `master` и деплоит (GitHub Pages) только владелец.

## Зоны в `index.html`

Почти весь сайт — один файл, поэтому параллельные задачи делят его по зонам. Чужую зону не правим: нужна правка — пишем её хозяину.

| Задача | Ветка | Зона |
|---|---|---|
| `menu-i18n` — меню на ҚАЗ/ENG | `worktree-menu-i18n` | оверлей меню: разметка `#menu-modal`, массивы `MENU_KITCHEN` / `MENU_BAR` / `MENU_DESSERT`, `MK`, `LEGEND`, `MENU_TABS` и функции отрисовки меню; стили `.mm-*`. Переключатель языка — только внутри оверлея меню. |
| `to-go` — 5-я точка bakery to go | `worktree-to-go` | `BRANCHES`, `renderLocations`, модалка выбора филиала (`#modal`), секции hero / strip / about / features / locations / contacts, `<head>` (title, description, og/twitter) — тексты про «4 кофейни» и «24/7». |

Общие стили (`:root`, базовые классы) — предупредить второго исполнителя перед правкой.

## Журнал приёмки

| Дата | Задача | Ветка | PR | Итог |
|---|---|---|---|---|
| 2026-10-06 | заведён журнал координации | `worktree-coordination` | #1 | слит 06.10 (merge по поручению владельца) |
| 2026-10-06 | `to-go` — 5-я точка bakery to go (заявка 71742) | `worktree-to-go` | #2 | принято, ждёт merge |
