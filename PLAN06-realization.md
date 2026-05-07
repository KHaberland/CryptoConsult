Агент 1 — модель Wallet
Добавь новую Django модель Wallet в приложении portfolios.

Требования:

* Связь с Portfolio (ForeignKey, related_name='wallets')
* Поля: name (CharField), type (choices), is_default (Boolean), note (CharField optional)
* created_at, updated_at (auto fields)
* unique_together: (portfolio, name)
* ordering: ['-is_default', 'name']

Типы:

* exchange, hot, cold, bank, other

Не изменяй другие модели. Только добавь Wallet.

Агент 2 — модель WalletHolding
Добавь модель WalletHolding в portfolios.

Требования:

* ForeignKey на Wallet (related_name='holdings')
* symbol (CharField)
* units (DecimalField max_digits=20, decimal_places=8)
* updated_at

unique_together: (wallet, symbol)

Важно:

* НЕ добавляй initial_price
* Это только баланс (units)

Не трогай другие модели.

Агент 3 — модель WalletTransfer

Добавь модель WalletTransfer.

Требования:

* portfolio (FK)
* from_wallet (FK)
* to_wallet (FK)
* symbol
* from_units
* to_units
* fee_units
* fee_usd
* occurred_on
* note
* created_at

Добавь ordering и индекс по (portfolio, occurred_on)

Не изменяй другие модели.


Агент 4 — модель HoldingAdjustment

Добавь модель HoldingAdjustment.

Требования:

* FK на WalletHolding
* units_before
* units_after
* delta
* value_delta_usd
* reason (choices)
* note
* occurred_on
* created_at

reason choices:
network_fee, exchange_fee, reconciliation, input_error, other

Не изменяй другие модели.


Агент 5 — миграции

Создай Django миграции для новых моделей:

* Wallet
* WalletHolding
* WalletTransfer
* HoldingAdjustment

Дополнительно:
создай пустую data migration для backfill default wallet.

Не реализуй backfill логику — только подготовь миграцию.

Агент 6 — backfill логика

Реализуй data migration:

Задача:

* для каждого Portfolio создать default Wallet (если нет)

* name = "Общий кошелёк"

* is_default = True

* для каждого PortfolioAsset:
  создать WalletHolding в default wallet
  symbol = asset.symbol
  units = asset.units

Важно:

* не дублировать holdings
* не ломать существующие данные

ЭТАП 2 — WalletLedger (самый важный)


Агент 7 — сервис WalletLedger


Создай класс WalletLedger в services.py.

Методы:

get_default_wallet
get_or_create_holding
add_units
aggregate_units
sync_aggregate
sync_all

Требования:

использовать Decimal (без float)
не терять точность
не менять другие сервисы

Важно:
PortfolioAsset.units = сумма WalletHolding.units


ЭТАП 3 — Transfer AP


Создай WalletTransferInputSerializer.

Поля:

* from_wallet_id
* to_wallet_id
* symbol
* from_units
* to_units

Валидация:

* from != to
* to_units <= from_units
* units > 0

Не трогай другие сериализаторы.

Агент 9 — WalletTransferView

Создай API view для перевода между кошельками.

POST /wallets/transfer/

Логика:

* списать units из from_wallet
* добавить units в to_wallet
* посчитать fee = from_units - to_units
* обновить агрегат через WalletLedger

Важно:

* использовать transaction.atomic
* проверять баланс


ЭТАП 4 — Adjustment

Создай API для ручной коррекции WalletHolding.

POST /wallets/{wallet_id}/holdings/{symbol}/adjust/

Логика:

* units_before → units_after
* delta = разница
* пересчитать PortfolioAsset через WalletLedger
* записать HoldingAdjustment

Важно:
Net Invested НЕ меняется


ЭТАП 5 — интеграция (самый аккуратный этап)

Агент 11 — contribute update


Обнови contribute_by_units:

* добавь wallet_id (optional)
* если нет → default wallet
* вместо изменения PortfolioAsset.units:
  использовать WalletLedger.add_units
* после — sync_aggregate

Не ломай существующую логику.


Агент 12 — swap update

Обнови swap:

* добавить wallet_id
* swap происходит внутри одного кошелька
* проверка баланса на конкретном кошельке
* использовать WalletLedger

Не использовать агрегатные units для проверки.


Агент 13 — withdraw update

Обнови withdraw:

* поддержка wallet_id
* если нет → выбрать кошелёк с max units
* списывать с WalletHolding
* затем sync_aggregate

Не менять Net Invested логику.


ЭТАП 6 — FRONTEND (разбито по агентам)
🔹 Агент F1 — API для кошельков


Добавь в api.ts поддержку кошельков.

Создай интерфейсы:

* WalletHolding
* Wallet
* WalletTransfer

Добавь методы:

* list wallets
* create wallet
* update wallet
* delete wallet
* transfer between wallets
* adjust holding

Не трогай остальной API.


Агент F2 — store (zustand или аналог)

Обнови portfolioStore:

Добавь:

* wallets: Wallet[]
* fetchWallets
* createWallet
* updateWallet
* deleteWallet
* transferBetweenWallets
* adjustHolding

После каждой мутации:

* обновлять wallets
* обновлять portfolio value

Не ломай существующую логику store.


Агент F3 — WalletCard компонент

Создай компонент WalletCard.

Показывает:

* название кошелька
* тип (биржа, холодный и т.д.)
* список активов (symbol + units + USD)
* total_value_usd

Добавь кнопки:

* редактировать
* удалить (если не default)

Сделай простой UI без сложной стилизации.


Агент F4 — список кошельков на дашборде


Добавь на dashboard новую секцию "Мои кошельки".

Требования:

* список WalletCard
* кнопка "Добавить кошелёк"
* кнопка "Перевести"

Расположить над таблицей активов.

Не ломать существующий dashboard.

Агент F5 — WalletFormModal

Создай модалку для создания/редактирования кошелька.

Поля:

* name
* type (select)
* note (optional)

Поддержка:

* create
* edit

Без сложного дизайна.


Агент F6 — TransferBetweenWalletsModal

Создай модалку перевода между кошельками.

Поля:

* from_wallet
* to_wallet
* symbol
* from_units
* to_units
* note

Логика:

* показывать доступный баланс
* считать fee = from_units - to_units
* показывать fee в UI

Отправка через API transfer.


Агент F7 — AdjustHoldingModal

Создай модалку коррекции баланса.

Поля:

* units_after
* reason (optional)
* note (optional)

Показывать:

* текущий баланс
* delta
* влияние на USD

Важно:
показать warning:
"Это изменит PnL. Net Invested не изменится."


Агент F8 — таблица активов (разрез по кошелькам)

Обнови таблицу активов:

Добавь колонку:

* Wallet

Показывать holdings по кошелькам (не агрегировано)

Добавь кнопку "редактировать" (иконка карандаш)
→ открывает AdjustHoldingModal

Не ломай существующую таблицу.


Агент F9 — WalletSelector (переиспользуемый)


Создай компонент WalletSelector.

Используется в:

* contribute
* swap
* withdraw

Логика:

* если 1 кошелёк → скрыть
* если несколько → select

Возвращает wallet_id.

Агент F10 — интеграция в ContributeModal

Обнови ContributeModal:

Добавь выбор кошелька (WalletSelector)

Передавай wallet_id в API

Не ломай существующую логику.


Агент F11 — интеграция в SwapModal

Обнови SwapModal:

Добавь WalletSelector

Важно:
показывать только те активы, которые есть на выбранном кошельке

Передавать wallet_id в API

Агент F12 — интеграция в WithdrawModal

Обнови WithdrawModal:

Добавь выбор кошелька для каждого актива

Если не выбран:
использовать кошелёк с максимальным балансом

Передавать wallet_id в API


ЭТАП 7 — ТЕСТЫ

Создай тесты для Wallet:

* создание
* дубликат имени
* обновление
* удаление пустого
* запрет удаления с балансом
* запрет удаления default

Используй pytest.

Агент T2 — тесты transfer
Создай тесты для WalletTransfer:

* обычный перевод
* перевод с комиссией
* недостаточный баланс
* to_units > from_units → ошибка
* перевод в тот же кошелёк → ошибка

Проверять:

* balances
* fee
* PortfolioAsset.units

Агент T3 — тесты adjustment

Создай тесты для HoldingAdjustment:

* уменьшение баланса
* увеличение баланса
* корректировка в 0
* запрет отрицательных значений

Проверять:

* delta
* value_delta
* PortfolioAsset.units

Агент T4 — тесты инварианта

Создай тест:

PortfolioAsset.units == сумма WalletHolding.units

Проверить после:

* contribute
* swap
* transfer
* adjustment

Агент T5 — тест миграции

Создай тест для data migration:

* был Portfolio без Wallet
* после миграции появился default wallet
* holdings созданы корректно

Проверить инвариант.










































