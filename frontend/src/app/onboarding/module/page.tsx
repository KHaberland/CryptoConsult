'use client'

import { useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import {
  ArrowLeft,
  BookOpen,
  Lightbulb,
  ChevronRight,
  Menu,
  X,
} from 'lucide-react'

const MENU_ITEMS = [
  { id: 'history', label: 'История рынка' },
  { id: 'assets', label: 'Основные активы' },
  { id: 'altcoins', label: 'Альткоины и риски' },
  { id: 'mechanics', label: 'Механика цены' },
  { id: 'cycles', label: 'Циклы' },
  { id: 'portfolio', label: 'Пример портфеля' },
  { id: 'mistakes', label: 'Ошибки' },
  { id: 'psychology', label: 'Психология' },
] as const

export default function OnboardingModulePage() {
  const router = useRouter()
  const [menuOpen, setMenuOpen] = useState(false)
  const contentRef = useRef<HTMLDivElement>(null)

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id)
    el?.scrollIntoView({ behavior: 'smooth' })
    setMenuOpen(false)
  }

  const handleBack = () => router.push('/onboarding/disclaimer')
  const handleNext = () => router.push('/onboarding/strategy')

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-white/95 backdrop-blur border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Button variant="secondary" size="sm" onClick={handleBack}>
              <ArrowLeft className="w-4 h-4 mr-1" />
              Назад
            </Button>
            <div className="hidden sm:flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-primary-600" />
              <h1 className="font-semibold text-gray-900">Системный вводный модуль</h1>
            </div>
          </div>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="sm:hidden p-2 rounded-lg hover:bg-gray-100"
          >
            {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        {/* Mobile menu */}
        {menuOpen && (
          <div className="sm:hidden border-t border-gray-200 bg-white p-4">
            <nav className="flex flex-wrap gap-2">
              {MENU_ITEMS.map((item) => (
                <button
                  key={item.id}
                  onClick={() => scrollToSection(item.id)}
                  className="px-3 py-2 rounded-lg bg-gray-100 hover:bg-primary-100 hover:text-primary-700 text-sm font-medium"
                >
                  {item.label}
                </button>
              ))}
            </nav>
          </div>
        )}
      </header>

      <div className="max-w-4xl mx-auto px-4 py-8 pb-24 flex gap-8">
        {/* Desktop sidebar */}
        <aside className="hidden sm:block w-56 flex-shrink-0">
          <nav className="sticky top-24 space-y-1">
            {MENU_ITEMS.map((item) => (
              <button
                key={item.id}
                onClick={() => scrollToSection(item.id)}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-sm font-medium text-gray-700 hover:bg-primary-50 hover:text-primary-700 transition-colors"
              >
                <ChevronRight className="w-4 h-4 text-gray-400" />
                {item.label}
              </button>
            ))}
          </nav>
        </aside>

        {/* Content */}
        <div ref={contentRef} className="flex-1 min-w-0 space-y-8">
          {/* История рынка */}
          <section id="history" className="scroll-mt-24">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-start gap-2 mb-4">
                  <Lightbulb className="w-6 h-6 text-amber-500 flex-shrink-0 mt-0.5" />
                  <h2 className="text-xl font-bold text-gray-900">История рынка</h2>
                </div>
                <p className="text-gray-700 mb-4">
                  💡 <strong>Крипторынок — новый класс активов</strong>
                </p>
                <p className="text-gray-600 mb-3">
                  В 2009 году появился Bitcoin — первая децентрализованная цифровая валюта.
                  В 2010 году его цена составляла около $0.003.
                </p>
                <p className="text-gray-600 mb-3">
                  В 2015 году был запущен Ethereum — платформа для смарт-контрактов и цифровых приложений.
                  Цена старта торгов — примерно $0.30–1.
                </p>
                <p className="text-gray-600 mb-4">
                  За 15 лет рынок прошёл путь от эксперимента разработчиков до глобального инвестиционного класса активов.
                </p>
                <div className="bg-primary-50 rounded-lg p-4 border border-primary-100">
                  <h3 className="font-semibold text-primary-800 mb-2">📈 Почему инвесторы рассматривают криптовалюты</h3>
                  <ul className="space-y-1 text-primary-700 text-sm">
                    <li>• Ограниченная эмиссия (например, у Bitcoin максимум 21 млн монет)</li>
                    <li>• Независимость от центральных банков</li>
                    <li>• Развитие новой цифровой экономики</li>
                    <li>• Возможность долгосрочного роста</li>
                  </ul>
                </div>
              </CardContent>
            </Card>
          </section>

          {/* Основные активы */}
          <section id="assets" className="scroll-mt-24">
            <Card>
              <CardContent className="pt-6">
                <h2 className="text-xl font-bold text-gray-900 mb-4">Основные активы</h2>
                <p className="text-gray-600 mb-3">
                  Bitcoin и Ethereum — два крупнейших криптоактива по капитализации.
                </p>
                <p className="text-gray-600">
                  Bitcoin — «цифровое золото», ограниченная эмиссия. Ethereum — платформа для смарт-контрактов, DeFi и Web3.
                </p>
              </CardContent>
            </Card>
          </section>

          {/* Альткоины и риски */}
          <section id="altcoins" className="scroll-mt-24">
            <Card>
              <CardContent className="pt-6">
                <h2 className="text-xl font-bold text-gray-900 mb-4">Альткоины и риски</h2>
                <p className="text-gray-600 mb-3">
                  🌐 <strong>Кроме Bitcoin и Ethereum</strong>
                </p>
                <p className="text-gray-600 mb-4">
                  Помимо двух крупнейших активов существуют тысячи других проектов — так называемые альткоины.
                  Например: Solana, Cardano, Polkadot. Они развивают новые технологии, скорость транзакций, совместимость блокчейнов.
                </p>
                <div className="bg-amber-50 rounded-lg p-4 border border-amber-100 mb-4">
                  <h3 className="font-semibold text-amber-800 mb-2">Почему они более рисковые?</h3>
                  <ul className="space-y-1 text-amber-700 text-sm">
                    <li>• Меньше капитализация</li>
                    <li>• Выше зависимость от команды и инвесторов</li>
                    <li>• Более резкие колебания цены</li>
                    <li>• Часть проектов со временем исчезает</li>
                  </ul>
                </div>
                <p className="text-gray-600">
                  <strong>Можно ли на них заработать?</strong> Да. В периоды роста рынка альткоины часто показывают более высокую доходность.
                  Но разумный подход — выделять на такие активы ограниченную долю портфеля.
                </p>
              </CardContent>
            </Card>
          </section>

          {/* Механика цены */}
          <section id="mechanics" className="scroll-mt-24">
            <Card>
              <CardContent className="pt-6">
                <h2 className="text-xl font-bold text-gray-900 mb-4">Механика цены</h2>
                <p className="text-gray-600 mb-3">
                  ⚙ <strong>Как формируется цена</strong>
                </p>
                <p className="text-gray-600 mb-3">
                  Цена меняется под влиянием: спроса и предложения, макроэкономики, регулирования, доверия инвесторов.
                </p>
                <p className="text-gray-600 mb-4">
                  Крипторынок волатилен. Просадки 20–50% возможны даже в рамках общего восходящего тренда.
                </p>
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <h3 className="font-semibold text-slate-800 mb-2">⛏ Кто такие майнеры</h3>
                  <p className="text-slate-700 text-sm mb-2">
                    Майнеры — участники сети, которые проверяют транзакции, объединяют их в блоки, добавляют в блокчейн.
                    За эту работу получают вознаграждение в виде новых монет и комиссий.
                  </p>
                  <p className="text-slate-600 text-sm italic">
                    Проще говоря: майнеры — это распределённый «бухгалтер» системы, который работает без центрального банка.
                  </p>
                </div>
                <div className="mt-4 bg-blue-50 rounded-lg p-4 border border-blue-100">
                  <h3 className="font-semibold text-blue-800 mb-2">🌍 Web3 и DeFi</h3>
                  <p className="text-blue-700 text-sm">
                    Web3 — интернет нового поколения, где пользователи владеют цифровыми активами через блокчейн.
                    DeFi — децентрализованные финансы (кредиты, обмен, депозиты) без банков, через смарт-контракты.
                  </p>
                </div>
                <div className="mt-4">
                  <h3 className="font-semibold text-gray-800 mb-2">🏦 Где приобретаются активы</h3>
                  <p className="text-gray-600 text-sm">
                    Крупные платформы: Binance, Coinbase, Kraken — обеспечивают покупку, продажу и хранение цифровых активов.
                  </p>
                </div>
              </CardContent>
            </Card>
          </section>

          {/* Циклы */}
          <section id="cycles" className="scroll-mt-24">
            <Card>
              <CardContent className="pt-6">
                <h2 className="text-xl font-bold text-gray-900 mb-4">Циклы крипторынка</h2>
                <p className="text-gray-600 mb-4">
                  Крипторынок развивается волнами. Исторически наблюдается модель примерно 4-летнего цикла, связанная с халвингом Bitcoin — сокращением награды майнерам вдвое каждые ~4 года.
                  Меньше новых монет → ниже предложение → при растущем спросе цена имеет потенциал к росту.
                </p>
                <div className="space-y-3 mb-4">
                  <div className="p-3 rounded-lg bg-green-50 border border-green-100">
                    <strong className="text-green-800">Накопление</strong>
                    <p className="text-green-700 text-sm mt-1">После падения рынок стабилизируется. Интерес низкий.</p>
                  </div>
                  <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-100">
                    <strong className="text-emerald-800">Рост (бычий рынок)</strong>
                    <p className="text-emerald-700 text-sm mt-1">Повышается интерес. Альткоины часто растут быстрее.</p>
                  </div>
                  <div className="p-3 rounded-lg bg-amber-50 border border-amber-100">
                    <strong className="text-amber-800">Перегрев</strong>
                    <p className="text-amber-700 text-sm mt-1">Эмоции, ажиотаж, нереалистичные ожидания.</p>
                  </div>
                  <div className="p-3 rounded-lg bg-red-50 border border-red-100">
                    <strong className="text-red-800">Снижение (медвежий рынок)</strong>
                    <p className="text-red-700 text-sm mt-1">Глубокая коррекция. «Очистка» слабых проектов.</p>
                  </div>
                </div>
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <h3 className="font-semibold text-slate-800 mb-2">🧠 Что важно понимать новичку</h3>
                  <ul className="space-y-1 text-slate-700 text-sm">
                    <li>• Рост не бывает линейным</li>
                    <li>• Сильные просадки — часть цикла</li>
                    <li>• Наибольшие риски в фазе перегрева</li>
                    <li>• Спокойствие и стратегия важнее краткосрочных эмоций</li>
                  </ul>
                  <p className="text-slate-600 text-sm mt-3 italic">
                    Цикличность не гарантирует повторение истории, но понимание фаз рынка помогает принимать более взвешенные решения.
                  </p>
                </div>
              </CardContent>
            </Card>
          </section>

          {/* Пример портфеля */}
          <section id="portfolio" className="scroll-mt-24">
            <Card>
              <CardContent className="pt-6">
                <h2 className="text-xl font-bold text-gray-900 mb-4">Пример портфеля</h2>
                <p className="text-gray-600 mb-4">
                  📊 <strong>Консервативный подход для новичка</strong>
                </p>
                <div className="space-y-3 mb-4">
                  <div className="flex items-center justify-between p-3 rounded-lg bg-orange-50 border border-orange-100">
                    <span className="font-medium text-orange-800">60% — Bitcoin</span>
                    <span className="text-orange-600 text-sm">Основа портфеля</span>
                  </div>
                  <div className="flex items-center justify-between p-3 rounded-lg bg-indigo-50 border border-indigo-100">
                    <span className="font-medium text-indigo-800">25% — Ethereum</span>
                    <span className="text-indigo-600 text-sm">Web3 и DeFi</span>
                  </div>
                  <div className="flex items-center justify-between p-3 rounded-lg bg-purple-50 border border-purple-100">
                    <span className="font-medium text-purple-800">10% — крупные альткоины</span>
                    <span className="text-purple-600 text-sm">Solana, Cardano</span>
                  </div>
                  <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50 border border-gray-200">
                    <span className="font-medium text-gray-800">5% — стейблкоины</span>
                    <span className="text-gray-600 text-sm">Резерв для докупок</span>
                  </div>
                </div>
                <p className="text-gray-600 text-sm">
                  Такой портфель не перегружен риском, ориентирован на долгосрочный рост, сохраняет баланс между стабильностью и потенциалом.
                  Конкретные пропорции зависят от горизонта и готовности к просадкам.
                </p>
              </CardContent>
            </Card>
          </section>

          {/* Ошибки */}
          <section id="mistakes" className="scroll-mt-24">
            <Card>
              <CardContent className="pt-6">
                <h2 className="text-xl font-bold text-gray-900 mb-4">Типичные ошибки новичков</h2>
                <ul className="space-y-2 text-gray-700">
                  <li className="flex items-start gap-2">
                    <span className="text-red-500">⚠</span>
                    <span><strong>Инвестирование последних денег</strong> — нужна финансовая подушка вне крипты.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-red-500">⚠</span>
                    <span><strong>Покупка на эмоциях</strong> — вход на пике из-за страха «упустить возможность».</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-red-500">⚠</span>
                    <span><strong>Отсутствие плана выхода</strong> — решения принимаются импульсивно.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-red-500">⚠</span>
                    <span><strong>Ставка на один актив</strong> — концентрация усиливает риски.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-red-500">⚠</span>
                    <span><strong>Постоянная проверка графиков</strong> — эмоциональное давление приводит к ошибочным действиям.</span>
                  </li>
                </ul>
              </CardContent>
            </Card>
          </section>

          {/* Психология */}
          <section id="psychology" className="scroll-mt-24">
            <Card>
              <CardContent className="pt-6">
                <h2 className="text-xl font-bold text-gray-900 mb-4">Психология инвестора</h2>
                <p className="text-gray-600 mb-4">
                  🛡 <strong>Управление риском и психология</strong>
                </p>
                <p className="text-gray-600 mb-4">
                  Крипторынок проверяет не только стратегию, но и характер.
                </p>
                <div className="bg-green-50 rounded-lg p-4 border border-green-100 mb-4">
                  <h3 className="font-semibold text-green-800 mb-2">🤝 Подход для начинающих</h3>
                  <ul className="space-y-1 text-green-700 text-sm">
                    <li>✔ не инвестировать последние средства</li>
                    <li>✔ входить постепенно (DCA)</li>
                    <li>✔ диверсифицировать портфель</li>
                    <li>✔ заранее определить стратегию выхода</li>
                    <li>✔ принимать решения без эмоций</li>
                  </ul>
                </div>
                <p className="text-gray-600 mb-3">
                  Важно: инвестировать на понятный срок (3–5 лет), быть готовым к просадкам, не менять стратегию при каждом новостном шуме.
                </p>
                <p className="text-gray-700 font-medium">
                  Главный риск — не волатильность. Главный риск — импульсивные решения.
                  Дисциплина и системность дают преимущество над эмоциями.
                </p>
                <p className="text-gray-600 text-sm mt-3 italic">
                  Это не инструмент для быстрых решений. Это часть современного инвестиционного портфеля при грамотном подходе.
                </p>
              </CardContent>
            </Card>
          </section>
        </div>
      </div>

      {/* Bottom navigation */}
      <div className="fixed bottom-0 left-0 right-0 bg-white/95 backdrop-blur border-t border-gray-200 p-4">
        <div className="max-w-4xl mx-auto flex justify-end">
          <Button onClick={handleNext} size="lg">
            Далее: стратегия
            <ChevronRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      </div>
    </main>
  )
}
