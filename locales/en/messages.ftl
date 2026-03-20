# Buttons
button.current-rates = ⏱️ Current Rates
button.subscribe = 🔔 Subscribe
button.unsubscribe = 🔕 Unsubscribe
button.language = 🌐 Language
button.converter = 💱 Converter
button.show-all = 📋 Show All
button.back-to-top = 🔝 Top 5
button.alert = 🚨 Alerts
button.chart = 📈 Chart
button.branch = 🏦 Nearest Branch

# Start
start.welcome = Hello! I'm KursBot — currency exchange rates for Uzbekistan banks. Choose a button below:

# Language
lang.select = Select language:
lang.saved = Language changed!
lang.uz-cy = 🇺🇿 O'zbekcha
lang.ru = 🇷🇺 Русский
lang.en = 🇬🇧 English

# Rates
rates.title = Currency Rates
rates.last-updated = Updated: { $time }
rates.top-banks = Top banks (sell)
rates.no-rates = No data for this currency
rates.page = Page { $current } of { $total }
rates.bank = Bank
rates.buy = Buy
rates.sell = Sell
rates.best-legend = Best: ↓ Buy, ↑ Sell.
rates.best-sell = Best sell ↑
rates.best-buy = Best buy ↓
rates.stale-warning = Stale data:
rates.disclaimer = Rates are for reference only. Verify with your bank before transacting.
rates.col-bank = bank
rates.col-sell = sell
rates.col-buy = buy

# Months
month.1 = January
month.2 = February
month.3 = March
month.4 = April
month.5 = May
month.6 = June
month.7 = July
month.8 = August
month.9 = September
month.10 = October
month.11 = November
month.12 = December

# Subscription
subscription.enabled = ✅ Subscribed! You'll receive daily rate digests.
subscription.disabled = ❌ Unsubscribed.
subscription.error = Error. Please try again.

# Digest schedule
schedule.prompt = Choose digest schedule:
schedule.morning = ☀️ Morning (09:00)
schedule.evening = 🌙 Evening (18:00)
schedule.twice = 🔄 Twice daily
schedule.off = ❌ Turn off
schedule.saved = Schedule set: { $schedule }

# Converter
converter.prompt = Select currency to convert:
converter.enter-amount = Enter amount in { $currency }:
converter.result = 💱 { $amount } { $currency } = { $result } UZS
📊 CBU rate: { $rate }
converter.error = Please enter a valid number.

# Unknown
unknown.use-buttons = I didn't understand. Please use the buttons below 👇

# Digest message
digest.title = 📈 Daily Currency Rates
digest.date = 📅 { $date }
digest.usd = 💵 USD: { $rate } sum
digest.eur = 💶 EUR: { $rate } sum
digest.rub = 🇷🇺 RUB: { $rate } sum
digest.footer = 🔄 Source: CBU

# Alerts
alert.set-currency = Select currency for alert:
alert.set-direction = Notify when sell rate:
alert.above = ⬆️ Goes above
alert.below = ⬇️ Goes below
alert.enter-threshold = Enter the threshold rate (e.g. 12800):
alert.created = ✅ Alert set! I'll notify you when { $code } sell { $direction } { $threshold }.
alert.invalid-number = Please enter a valid number.
alert.list-title = 🔔 Your active alerts:
alert.list-empty = No active alerts. Use /alert to set one.
alert.list-item = { $code } sell { $direction } { $threshold }
alert.deleted = ✅ Alert removed.
alert.triggered = 🚨 Alert! { $code } sell rate is now { $rate } ({ $direction } { $threshold }).
alert.limit = You can have up to 5 active alerts.

# Chart
chart.title = 📊 { $code } Rate Trend ({ $days } days)
chart.no-data = No historical data for { $code } yet.

# Branch finder
branch.prompt = Send your location and I'll show nearby branches of banks with the best rates:
branch.header = Banks with best { $code } rates near you:
branch.open-map = Open map
branch.choose-map = Choose a map app to find branches:
branch.no-location = Please share your location using the button below.

# Auto-post
autopost.only-groups = This command works only in groups and channels. Add the bot as admin to your channel/group, then use /autopost there.
autopost.admin-only = Only group/channel admins can configure auto-posting.
autopost.need-post-permission = Please give the bot permission to post messages in this channel.
autopost.configure = ⚙️ Configure auto-posting for this chat.
    Choose schedule and language:
autopost.choose-lang = Choose the language for auto-post messages:
autopost.removed = ✅ Auto-posting disabled for this chat.
autopost.error = Something went wrong. Please try again.
