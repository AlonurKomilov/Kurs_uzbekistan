# Buttons
button.current-rates = ⏱️ Текущий курс
button.subscribe = 🔔 Подписаться
button.unsubscribe = 🔕 Отписаться
button.language = 🌐 Язык
button.converter = 💱 Конвертер
button.show-all = 📋 Показать все
button.back-to-top = 🔝 Топ 5

# Start
start.welcome = Привет! Я KursBot — курсы валют банков Узбекистана. Выберите кнопку:

# Language
lang.select = Выберите язык:
lang.saved = Язык изменен!
lang.uz-cy = 🇺🇿 O'zbekcha
lang.ru = 🇷🇺 Русский
lang.en = 🇬🇧 English

# Rates
rates.title = Курсы валют
rates.last-updated = Обновлено: { $time }
rates.top-banks = Топ банков (продажа)
rates.no-rates = Нет данных по этой валюте
rates.page = Страница { $current } из { $total }
rates.bank = Банк
rates.buy = Покупка
rates.sell = Продажа
rates.best-legend = Лучшая: ↓ Покупка, ↑ Продажа.
rates.best-sell = Лучшая продажа ↑
rates.best-buy = Лучшая покупка ↓
rates.stale-warning = Устаревшие данные:
rates.disclaimer = Курсы носят справочный характер. Уточняйте в банке.
rates.col-bank = банк
rates.col-sell = прод
rates.col-buy = покуп

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
subscription.enabled = ✅ Подписка включена! Вы будете получать ежедневные курсы.
subscription.disabled = ❌ Подписка отключена.
subscription.error = Ошибка. Попробуйте ещё раз.

# Digest schedule
schedule.prompt = Выберите расписание:
schedule.morning = ☀️ Утро (09:00)
schedule.evening = 🌙 Вечер (18:00)
schedule.twice = 🔄 Дважды в день
schedule.off = ❌ Отключить
schedule.saved = Расписание: { $schedule }

# Converter
converter.prompt = Выберите валюту для конвертации:
converter.enter-amount = Введите сумму в { $currency }:
converter.result = 💱 { $amount } { $currency } = { $result } сум
📊 Курс ЦБ: { $rate }
converter.error = Пожалуйста, введите корректное число.

# Unknown
unknown.use-buttons = Не понял. Пожалуйста, используйте кнопки ниже 👇

# Digest message
digest.title = 📈 Ежедневный курс валют
digest.date = 📅 { $date }
digest.usd = 💵 USD: { $rate } сум
digest.eur = 💶 EUR: { $rate } сум
digest.rub = 🇷🇺 RUB: { $rate } сум
digest.footer = 🔄 Источник: ЦБ РУз

# Alerts
alert.set-currency = Выберите валюту для уведомления:
alert.set-direction = Уведомить когда курс продажи:
alert.above = ⬆️ Поднимется выше
alert.below = ⬇️ Опустится ниже
alert.enter-threshold = Введите пороговый курс (напр: 12800):
alert.created = ✅ Уведомление установлено! Сообщу когда { $code } продажа { $direction } { $threshold }.
alert.invalid-number = Пожалуйста, введите корректное число.
alert.list-title = 🔔 Ваши активные уведомления:
alert.list-empty = Нет активных уведомлений. Используйте /alert.
alert.list-item = { $code } продажа { $direction } { $threshold }
alert.deleted = ✅ Уведомление удалено.
alert.triggered = 🚨 Внимание! Курс { $code } продажи сейчас { $rate } ({ $direction } { $threshold }).
alert.limit = Максимум 5 активных уведомлений.

# Chart
chart.title = 📊 Тренд { $code } ({ $days } дней)
chart.no-data = Нет исторических данных по { $code }.

# Branch finder
branch.prompt = Отправьте местоположение и я покажу ближайшие отделения банков с лучшими курсами:
branch.header = Банки с лучшим курсом { $code } рядом с вами:
branch.open-map = Открыть карту
branch.choose-map = Выберите картовое приложение для поиска отделений:
branch.no-location = Пожалуйста, отправьте геолокацию через кнопку ниже.

# Auto-post
autopost.only-groups = Эта команда работает только в группах и каналах. Добавьте бота админом в ваш канал/группу, затем используйте /autopost там.
autopost.admin-only = Только администраторы группы/канала могут настроить авто-публикацию.
autopost.need-post-permission = Пожалуйста, дайте боту разрешение на публикацию сообщений в этом канале.
autopost.configure = ⚙️ Настройте авто-публикацию для этого чата.
    Выберите расписание и язык:
autopost.choose-lang = Выберите язык для авто-публикаций:
autopost.removed = ✅ Авто-публикация отключена для этого чата.
autopost.error = Что-то пошло не так. Попробуйте ещё раз.
