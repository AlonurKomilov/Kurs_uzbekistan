# Buttons
button.current-rates = ⏱️ Ҳозирги курс
button.subscribe = 🔔 Обуна бўлиш
button.unsubscribe = 🔕 Обунани бекор қилиш
button.language = 🌐 Тил
button.converter = 💱 Конвертер
button.show-all = 📋 Ҳаммаси
button.back-to-top = 🔝 Топ 5
button.alert = 🚨 Огоҳлантириш
button.chart = 📈 Диаграмма
button.branch = 🏦 Яқин банк

# Start
start.welcome = Ассалому алайкум! Мен KursBot — Ўзбекистон банкларининг валюта курслари. Қуйидаги тугмалардан бирини танланг:

# Language
lang.select = Тилни танланг:
lang.saved = Тил ўзгартирилди!
lang.uz-cy = 🇺🇿 O'zbekcha
lang.ru = 🇷🇺 Русский
lang.en = 🇬🇧 English

# Rates
rates.title = Валюта курслари
rates.last-updated = Янгиланди: { $time }
rates.top-banks = Энг яхши банклар (сотиш)
rates.no-rates = Ушбу валюта бўйича маълумот йўқ
rates.page = { $current }-саҳифа { $total } дан
rates.bank = Банк
rates.buy = Олиш
rates.sell = Сотиш
rates.best-legend = Энг яхши: ↓ Олиш, ↑ Сотиш.
rates.best-sell = Энг яхши сотиш ↑
rates.best-buy = Энг яхши олиш ↓
rates.stale-warning = Эскирган маълумотлар:
rates.disclaimer = Курслар фақат маълумот учун. Амалиётдан олдин банкдан аниқлаштиринг.
rates.col-bank = банк
rates.col-sell = сотиш
rates.col-buy = олиш

# Months
month.1 = Январь
month.2 = Февраль
month.3 = Март
month.4 = Апрель
month.5 = Май
month.6 = Июнь
month.7 = Июль
month.8 = Август
month.9 = Сентябрь
month.10 = Октябрь
month.11 = Ноябрь
month.12 = Декабрь

# Subscription
subscription.enabled = ✅ Обуна ёқилди! Ҳар куни курс юборилади.
subscription.disabled = ❌ Обуна ўчирилди.
subscription.error = Хатолик. Қайта уриниб кўринг.

# Digest schedule
schedule.prompt = Курс юбориш вақтини танланг:
schedule.morning = ☀️ Эрталаб (09:00)
schedule.evening = 🌙 Кечқурун (18:00)
schedule.twice = 🔄 Кунига 2 марта
schedule.off = ❌ Ўчириш
schedule.saved = Расписание: { $schedule }

# Converter
converter.prompt = Конвертация қилиш учун валютани танланг:
converter.enter-amount = { $currency } миқдорини киритинг:
converter.result = 💱 { $amount } { $currency } = { $result } сўм
📊 МБ курси: { $rate }
converter.error = Илтимос, тўғри рақам киритинг.

# Unknown
unknown.use-buttons = Тушунмадим. Қуйидаги тугмалардан фойдаланинг 👇

# Digest message
digest.title = 📈 Кунлик валюта курси
digest.date = 📅 { $date }
digest.usd = 💵 АҚШ доллари: { $rate } сўм
digest.eur = 💶 Евро: { $rate } сўм
digest.rub = 🇷🇺 Рубль: { $rate } сўм
digest.footer = 🔄 Манба: МБ

# Alerts
alert.set-currency = Билдиришнома учун валютани танланг:
alert.set-direction = Сотиш курси қачон:
alert.above = ⬆️ Кўтарилса
alert.below = ⬇️ Тушса
alert.enter-threshold = 💱 Ҳозирги <b>{ $code }</b> сотиш курси: <b>{ $rate }</b>

Чегара курсини киритинг:
alert.created = ✅ Билдиришнома ўрнатилди! { $code } сотиш { $direction } { $threshold } бўлганда хабар бераман.
alert.invalid-number = Илтимос, тўғри рақам киритинг.
alert.list-title = 🔔 Билдиришномаларингиз:
alert.list-empty = Фаол билдиришнома йўқ. /alert буйруғини ишлатинг.
alert.list-item = { $code } сотиш { $direction } { $threshold }
alert.deleted = ✅ Билдиришнома ўчирилди.
alert.triggered = 🚨 Диққат! { $code } сотиш курси ҳозир { $rate } ({ $direction } { $threshold }).
alert.limit = Максимум 5 та фаол билдиришнома.

# Chart
chart.title = 📊 { $code } тренди ({ $days } кун)
chart.no-data = { $code } бўйича тарихий маълумот йўқ.

# Branch finder
branch.prompt = Жойлашувингизни юборинг ва мен энг яхши курсли банкларнинг яқин филиалларини кўрсатаман:
branch.header = Яқинингиздаги энг яхши { $code } курсли банклар:
branch.open-map = Харитани очиш
branch.choose-map = Филиалларни топиш учун харита иловасини танланг:
branch.no-location = Илтимос, қуйидаги тугма орқали жойлашувингизни юборинг.

# Auto-post
autopost.only-groups = Бу буйруқ фақат гуруҳ ва каналларда ишлайди. Ботни канал/гуруҳга админ сифатида қўшинг, кейин у ерда /autopost бўйруғини ишлатинг.
autopost.admin-only = Фақат гуруҳ/канал админлари авто-пост созлай олади.
autopost.need-post-permission = Илтимос, ботга бу каналда хабар юбориш рухсатини беринг.
autopost.configure = ⚙️ Бу чат учун авто-постни созланг.
    Жадвал ва тилни танланг:
autopost.choose-lang = Авто-пост хабарлари учун тилни танланг:
autopost.removed = ✅ Бу чат учун авто-пост ўчирилди.
autopost.error = Хатолик юз берди. Илтимос, қайтадан уриниб кўринг.
